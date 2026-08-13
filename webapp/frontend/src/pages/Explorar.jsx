import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiStream, descargar, ErrorApi, esNativo, fmtScore, getBase, getClaveIA, getEmail, getEndpointIA, getModeloIA, getProveedorIA, setEmail } from "../api.js";
import { Aviso, etiquetasOla, Idioma, Kpis, Ola, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, setCorridaId, setCorridaLocal, useCorrida } from "../estado.js";
import { getIdioma, t } from "../i18n/index.js";

// El orden es el del pipeline (cliente_ia/modelos.py:FASES) y es el que se
// numera 1..6 en pantalla.
const FASES = ["investigar", "competencia", "campanas", "prospectos", "decisores", "emails"];
const CUANTOS_EN_RESUMEN = 6;

function Fase({ n, clave, paso, abierta, alternar, children }) {
  const estado = paso?.estado || "pendiente";
  const hay = (paso?.items || 0) > 0;
  return (
    <section className={`fase ${estado} ${abierta ? "abierta on" : ""}`}>
      <button className="fase-cab" onClick={alternar} aria-expanded={abierta}>
        <span className="fase-num">{estado === "listo" ? "✓" : n}</span>
        <span className="fase-txt">
          <b>{t(`fase.${clave}.n`)}</b>
          <small>{paso?.detalle || t(`fase.${clave}.d`)}</small>
        </span>
        <span className="fase-meta">
          {estado === "corriendo" ? <i className="latido" /> : null}
          {hay ? <span className="tnum">{paso.items}</span> : null}
          {paso?.ms ? <span className="ms tnum">{paso.ms} ms</span> : null}
          <span className="chev">⌄</span>
        </span>
      </button>
      {abierta ? <div className="fase-cuerpo">{children}</div> : null}
    </section>
  );
}

function DatoEmpresa({ etiqueta, valor }) {
  if (!valor || (Array.isArray(valor) && !valor.length)) return null;
  return (
    <p style={{ margin: "0 0 10px", fontSize: 13 }}>
      <span style={{ color: "var(--muted)", fontWeight: 700 }}>{etiqueta}: </span>
      {Array.isArray(valor) ? valor.join(" · ") : valor}
    </p>
  );
}

export default function Explorar() {
  const nav = useNavigate();
  const [id, setId] = useState(getCorridaId());
  const { corrida, error } = useCorrida(id);
  const [form, setForm] = useState({
    dominio: "mvkobranzaia.com", nombre: "MV Kobra AI", modo: "demo", prospectos: 50,
    // Recorte geográfico: "todos" mantiene el país propio primero en
    // proporción; "local" es para productos que exigen presencia física.
    mercado: "todos",
    // País propio del cliente: el que va primero en las tres olas. Vacío = que
    // lo deduzca el backend del TLD del dominio.
    pais: "",
    // Enlaces del mensaje: el banner, el video y la web que llevan el correo y
    // el mensaje de LinkedIn, cada uno en el idioma del receptor.
    sitio: "", video_en_landing: true, videos: { es: "", pt: "", en: "" },
  });
  const [verEnlaces, setVerEnlaces] = useState(false);
  // El backend dice qué modos puede correr de verdad: sin ANTHROPIC_API_KEY
  // el modo con IA no se ofrece (caería en silencio a «leer mi sitio» y el
  // usuario creería que la IA no busca nada — pasó en el despliegue público).
  const [salud, setSalud] = useState(null);
  useEffect(() => { api("/api/salud").then(setSalud).catch(() => {}); }, []);
  // Catálogo mundial de países y las olas vistas desde el elegido. Se vuelve a
  // pedir al cambiar el país porque las etiquetas del filtro de mercado dicen
  // el nombre del país y el de SU región, no "LATAM" para todo el mundo.
  const [geo, setGeo] = useState(null);
  useEffect(() => {
    api(`/api/geo?idioma=${getIdioma()}`
        + (form.pais ? `&pais=${form.pais}` : ""))
      .then(setGeo).catch(() => {});
  }, [form.pais]);
  const nombrePais = geo?.pais_base_nombre || "";
  const nombreRegion = geo?.region_base || "";
  // Los países del selector llegan ya ordenados por región; se agrupan acá
  // para poder pintarlos en <optgroup> sin recorrer la lista tres veces.
  const porRegion = (geo?.paises || []).reduce((acc, p) => {
    (acc[p.region_nombre] ||= []).push(p);
    return acc;
  }, {});
  // Cupo gratis de la web pública: cuántas búsquedas reales quedan. Se pide
  // con el correo guardado para que el del dueño se vea sin límite.
  const [cupo, setCupo] = useState(null);
  const [email, setEmailLocal] = useState(getEmail());
  const traerCupo = () => api("/api/cupo"
    + (getEmail() ? `?email=${encodeURIComponent(getEmail())}` : ""))
    .then(setCupo).catch(() => {});
  useEffect(() => { traerCupo(); }, []);
  // El modo IA se ofrece si el servidor puede correrlo (tiene clave propia) o
  // si el usuario pegó la suya en Configuración: en ese caso la clave viaja
  // con la corrida. Antes de la respuesta de salud se muestra, como siempre.
  const hayLLM = !salud || Boolean(salud.modos?.includes("llm")) || Boolean(getClaveIA());
  // Con clave propia pegada, el costo de la IA lo paga el usuario en su
  // propia cuenta: el servidor no cobra cupo ni pide correo por esa corrida
  // (webapp/backend/api.py:crear_corrida). La interfaz refleja lo mismo para
  // no pedir de más ni mostrar un aviso de límite que no aplica.
  const propiaClave = form.modo === "llm" && Boolean(getClaveIA());
  // Si el servidor no ofrece IA y el modo elegido era «llm», se baja a «web»
  // en vez de dejar el select apuntando a una opción que ya no existe.
  useEffect(() => {
    if (salud && !hayLLM) {
      setForm((f) => (f.modo === "llm" ? { ...f, modo: "web" } : f));
    }
  }, [salud, hayLLM]);
  const [lanzando, setLanzando] = useState(false);
  const [errLanzar, setErrLanzar] = useState("");
  const [abierta, setAbierta] = useState("investigar");
  const [tocada, setTocada] = useState(false);

  const pasos = Object.fromEntries((corrida?.pasos || []).map((p) => [p.clave, p]));
  const hechas = (corrida?.pasos || []).filter((p) => p.estado === "listo").length;
  const corriendo = corrida?.estado === "corriendo" || corrida?.estado === "pendiente";

  // Mientras corre, la fase abierta sigue a la que está trabajando — es lo que
  // hace que se vea como un proceso y no como una lista estática. En cuanto el
  // usuario abre una a mano deja de moverse solo (`tocada`).
  useEffect(() => {
    if (tocada || !corrida) return;
    const activa = (corrida.pasos || []).find((p) => p.estado === "corriendo");
    if (activa) setAbierta(activa.clave);
    else if (corrida.estado === "listo") setAbierta("prospectos");
  }, [corrida, tocada]);

  const lanzar = async (e) => {
    e.preventDefault();
    setErrLanzar("");
    setLanzando(true);
    setEmail(email);                     // queda para la próxima visita
    try {
      const cuerpo = {
        dominio: form.dominio.trim(),
        nombre: form.nombre.trim(),
        modo: form.modo,
        mercado: form.mercado,
        pais: form.pais,
        idioma: "es",
        prospectos: Number(form.prospectos) || 60,
        sitio: form.sitio.trim() || form.dominio.trim(),
        video_en_landing: form.video_en_landing,
        videos: Object.fromEntries(
          Object.entries(form.videos).filter(([, v]) => v.trim())),
        // El correo sólo hace falta para las búsquedas reales de la web
        // pública (cuenta el cupo gratis; el del dueño no descuenta).
        ...(form.modo !== "demo" && email.trim() ? { email: email.trim() } : {}),
        // La clave sólo viaja cuando la corrida la necesita; el proveedor, el
        // endpoint (Copilot/Azure) y el modelo elegido acompañan para que el
        // servidor sepa a qué API y con qué modelo llamar con ella.
        ...(form.modo === "llm" && getClaveIA()
          ? { clave_ia: getClaveIA(), proveedor_ia: getProveedorIA(),
              endpoint_ia: getEndpointIA(), modelo_ia: getModeloIA(getProveedorIA()) }
          : {}),
      };
      let r;
      if (salud?.sin_estado) {
        // Sin estado, la corrida llega POR FASES (streaming NDJSON): cada
        // línea es la corrida hasta ese momento, se guarda y la pantalla se
        // va pintando — empresa, competidores, campañas, prospectos…
        setTocada(false);
        r = await apiStream("/api/corridas?stream=1", cuerpo, (parcial) => {
          if (parcial && parcial.id) {
            setCorridaLocal(parcial);
            setCorridaId(parcial.id);
            setId(parcial.id);
          }
        });
        if (r && r.estado === "error") {
          throw new ErrorApi(r.error || "La corrida falló", 502);
        }
      } else {
        r = await api("/api/corridas", { metodo: "POST", cuerpo });
        if (r.estado === "listo" || r.pasos?.length) setCorridaLocal(r);
      }
      if (r && r.id) {
        setCorridaId(r.id);
        setId(r.id);
      }
      setTocada(false);
      setAbierta(r && r.estado === "listo" ? "prospectos" : "investigar");
      traerCupo();                       // la búsqueda real pudo gastar cupo
    } catch (e2) {
      setErrLanzar(e2.status === 0 && esNativo() && !getBase()
        ? t("aviso.sin_servidor") : `${t("explorar.error")}: ${e2.message}`);
    } finally {
      setLanzando(false);
    }
  };

  const nuevo = () => {
    setCorridaId("");
    setId("");
    setTocada(false);
  };

  const alternar = (clave) => {
    setTocada(true);
    setAbierta((a) => (a === clave ? "" : clave));
  };

  const r = corrida?.resumen || {};
  const porNivel = r.prospectos_por_nivel || {};

  return (
    <>
      <h1 className="page-title">{t("explorar.titulo")}</h1>
      <p className="page-sub">{t("explorar.subtitulo")}</p>

      {esNativo() && !getBase() ? <Aviso>{t("aviso.sin_servidor")}</Aviso> : null}

      <form className="card arranque" onSubmit={lanzar}>
        <div className="campo crece">
          <label htmlFor="dominio">{t("explorar.dominio")}</label>
          <input id="dominio" type="text" value={form.dominio} required
                 placeholder={t("explorar.dominio_ph")} autoCapitalize="none" autoCorrect="off"
                 onChange={(e) => setForm({ ...form, dominio: e.target.value })} />
        </div>
        <div className="campo">
          <label htmlFor="nombre">{t("explorar.nombre")}</label>
          <input id="nombre" type="text" value={form.nombre}
                 placeholder={t("explorar.nombre_ph")}
                 onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
        </div>
        <div className="campo">
          <label htmlFor="modo">{t("explorar.modo")}</label>
          <select id="modo" value={form.modo}
                  onChange={(e) => setForm({ ...form, modo: e.target.value })}>
            <option value="demo">{t("explorar.modo_demo")}</option>
            <option value="web">{t("explorar.modo_web")}</option>
            {hayLLM ? <option value="llm">{t("explorar.modo_llm")}</option> : null}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="pais">{t("explorar.pais")}</label>
          <select id="pais" value={form.pais}
                  onChange={(e) => setForm({ ...form, pais: e.target.value })}>
            <option value="">{t("explorar.pais_auto")}</option>
            {Object.entries(porRegion).map(([region, paises]) => (
              <optgroup key={region} label={region}>
                {paises.map((p) => (
                  <option key={p.codigo} value={p.codigo}>{p.nombre}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="mercado">{t("explorar.mercado")}</label>
          {/* Las etiquetas nombran el país y la región del cliente: decir
              "sólo LATAM" a alguien que vende en Alemania no significaba nada. */}
          <select id="mercado" value={form.mercado}
                  onChange={(e) => setForm({ ...form, mercado: e.target.value })}>
            <option value="todos">{t("explorar.mercado_todos", { pais: nombrePais })}</option>
            <option value="local">{t("explorar.mercado_local", { pais: nombrePais })}</option>
            <option value="regional">{t("explorar.mercado_regional", { region: nombreRegion })}</option>
            <option value="mundo">{t("explorar.mercado_mundo")}</option>
          </select>
        </div>
        <div className="campo">
          <label htmlFor="cuantos">{t("explorar.prospectos")}</label>
          <select id="cuantos" value={form.prospectos}
                  onChange={(e) => setForm({ ...form, prospectos: e.target.value })}>
            {[50, 100, 200, 500, 1000].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        {/* Las búsquedas reales gratis de la web piden un correo válido:
            cuenta el cupo por correo además de por navegador/IP. Con clave
            propia no hay cupo que cuidar, así que tampoco hace falta. */}
        {cupo?.pide_email && form.modo !== "demo" && !propiaClave ? (
          <div className="campo crece">
            <label htmlFor="email-cupo">{t("explorar.email")}</label>
            <input id="email-cupo" type="email" value={email} required
                   placeholder="vos@tuempresa.com" autoCapitalize="none"
                   autoCorrect="off" spellCheck="false"
                   onChange={(e) => setEmailLocal(e.target.value)} />
          </div>
        ) : null}
        <button className="btn cta" type="submit" disabled={lanzando || corriendo}>
          {lanzando || corriendo ? t("explorar.lanzando") : t("explorar.lanzar")} →
        </button>
        {corrida ? (
          <button className="btn ghost" type="button" onClick={nuevo}>{t("explorar.otra")}</button>
        ) : null}

        <div className="enlaces-cfg">
          <button type="button" className="desplegar"
                  onClick={() => setVerEnlaces(!verEnlaces)} aria-expanded={verEnlaces}>
            {verEnlaces ? "▾" : "▸"} {t("explorar.enlaces")}
          </button>
          {verEnlaces ? (
            <div className="enlaces-cuerpo">
              <div className="campo crece">
                <label htmlFor="sitio">{t("explorar.sitio")} <i>({t("explorar.opcional")})</i></label>
                <input id="sitio" type="text" value={form.sitio} inputMode="url"
                       autoCapitalize="none" autoCorrect="off"
                       placeholder={form.dominio || "mvkobranzaia.com"}
                       onChange={(e) => setForm({ ...form, sitio: e.target.value })} />
              </div>
              <label className="checkbox">
                <input type="checkbox" checked={form.video_en_landing}
                       onChange={(e) => setForm({ ...form, video_en_landing: e.target.checked })} />
                <span>{t("explorar.usar_video")}</span>
              </label>
              {["es", "pt", "en"].map((i) => (
                <div className="campo crece" key={i}>
                  <label htmlFor={`video-${i}`}>
                    {t("explorar.video_url", { idioma: i.toUpperCase() })}{" "}
                    <i>({t("explorar.opcional")})</i>
                  </label>
                  <input id={`video-${i}`} type="text" inputMode="url"
                         autoCapitalize="none" autoCorrect="off"
                         value={form.videos[i]} placeholder="https://…"
                         onChange={(e) => setForm({
                           ...form, videos: { ...form.videos, [i]: e.target.value } })} />
                </div>
              ))}
              <p className="nota" style={{ marginTop: 0 }}>{t("explorar.ayuda_video")}</p>
            </div>
          ) : null}
        </div>
      </form>

      {salud && !hayLLM ? <p className="nota">{t("explorar.modo_llm_falta")}</p> : null}

      {/* Aviso del cupo gratis de la web: cuántas búsquedas reales quedan y
          qué pasa cuando se terminan. El dueño no lo ve, y con clave propia
          tampoco aplica — la corrida no gasta cupo del servidor. */}
      {propiaClave ? (
        <p className="nota">{t("explorar.cupo_clave_propia")}</p>
      ) : cupo?.aplica && !cupo.owner ? (
        cupo.usadas >= cupo.gratis ? (
          <p className="nota">
            {t("explorar.cupo_agotado", { total: cupo.gratis })}{" "}
            <a href="/#precios">{t("explorar.cupo_comprar")}</a>
          </p>
        ) : (
          <p className="nota">
            {t("explorar.cupo_restante", { quedan: cupo.gratis - cupo.usadas, total: cupo.gratis })}
          </p>
        )
      ) : null}

      {/* La corrida con IA es una sola petición larga: sin este cartel el
          usuario ve "Buscando…" un par de minutos y asume que se colgó. */}
      {lanzando && form.modo === "llm" ? (
        <p className="nota">{t("explorar.llm_esperando")}</p>
      ) : null}

      {errLanzar ? <p className="error-note">{errLanzar}</p> : null}
      {error ? <p className="error-note">{error}</p> : null}
      {corrida?.error ? <p className="error-note">{corrida.error}</p> : null}

      {corrida ? (
        <>
          <div className="progreso" aria-label={t("explorar.progreso", { hechas, total: 6 })}>
            <i style={{ width: `${(hechas / FASES.length) * 100}%` }} />
          </div>

          {corrida.estado === "listo" ? (
            <div style={{ marginTop: 18 }}>
              <Kpis items={[
                { label: t("kpi.prospectos"), valor: r.prospectos || 0,
                  delta: `${t("kpi.uruguay")}: ${porNivel.local || 0}` },
                { label: t("kpi.decisores"), valor: r.decisores || 0 },
                { label: t("kpi.correos"), valor: r.correos ?? r.emails ?? 0,
                  delta: Object.entries(r.emails_por_idioma || {})
                    .map(([k, v]) => `${k.toUpperCase()} ${v}`).join(" · ") },
                { label: t("kpi.competidores"), valor: r.competidores || 0 },
                { label: t("kpi.campanas"), valor: r.campanas || 0 },
              ]} />
            </div>
          ) : null}

          {corrida.estado === "listo" && (corrida.prospectos || []).some((p) => p.sintetico) ? (
            <div style={{ marginTop: 16 }}><Aviso>{t("aviso.sintetico")}</Aviso></div>
          ) : null}

          {/* Fallos que la cadena de proveedores absorbió (p. ej. la IA falló
              y la cubrió el demo): sin esto, una corrida "con IA" que terminó
              en datos sintéticos parece rota sin explicación. */}
          {(corrida.avisos || []).length ? (
            <div style={{ marginTop: 16 }}>
              <Aviso>
                {t("aviso.avisos_corrida")}
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {corrida.avisos.map((a, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>{a}</li>
                  ))}
                </ul>
              </Aviso>
            </div>
          ) : null}

          <div className="fases">
            {/* 1 · investigar */}
            <Fase n={1} clave="investigar" paso={pasos.investigar}
                  abierta={abierta === "investigar"} alternar={() => alternar("investigar")}>
              {corrida.empresa ? (
                <>
                  <DatoEmpresa etiqueta={t("empresa.categoria")} valor={corrida.empresa.categoria} />
                  <DatoEmpresa etiqueta={t("empresa.propuesta")} valor={corrida.empresa.propuesta} />
                  <DatoEmpresa etiqueta={t("empresa.mercado")}
                               valor={corrida.pais_base_nombre || corrida.empresa.pais} />
                  <DatoEmpresa etiqueta={t("empresa.tamano")} valor={corrida.empresa.tamano_objetivo} />
                  <DatoEmpresa etiqueta={t("empresa.sectores")} valor={corrida.empresa.sectores_objetivo} />
                  <DatoEmpresa etiqueta={t("empresa.diferenciales")} valor={corrida.empresa.diferenciales} />
                </>
              ) : <Vacio texto={t("common.cargando")} />}
            </Fase>

            {/* 2 · competencia */}
            <Fase n={2} clave="competencia" paso={pasos.competencia}
                  abierta={abierta === "competencia"} alternar={() => alternar("competencia")}>
              {(corrida.competidores || []).length ? (
                <div className="comp-grid">
                  {corrida.competidores.map((c) => (
                    <div className="comp" key={c.dominio}>
                      <span className="fav">{(c.nombre || c.dominio)[0].toUpperCase()}</span>
                      <span className="dom" title={c.posicionamiento}>{c.dominio}</span>
                      {/* El país a la vista: es lo que permite VER que el
                          filtro de mercado se aplicó (o leer el aviso si
                          ningún competidor tiene base local). */}
                      {c.pais ? <span className="pill mundo">{c.pais}</span> : null}
                      <span className="sol tnum">{Math.round((c.solapamiento || 0) * 100)}%</span>
                    </div>
                  ))}
                </div>
              ) : <Vacio texto={t("common.cargando")} />}
            </Fase>

            {/* 3 · campañas */}
            <Fase n={3} clave="campanas" paso={pasos.campanas}
                  abierta={abierta === "campanas"} alternar={() => alternar("campanas")}>
              <p className="nota" style={{ marginTop: 0, marginBottom: 12 }}>
                {t("ola.explicacion")}
              </p>
              {(corrida.campanas || []).length ? (
                <div className="camp-grid">
                  {corrida.campanas.map((c) => (
                    <div className="camp" key={c.id}>
                      <b>{c.sector} <Ola nivel={c.nivel} etiquetas={etiquetasOla(corrida)} /></b>
                      <p>{c.angulo}</p>
                    </div>
                  ))}
                </div>
              ) : <Vacio texto={t("common.cargando")} />}
            </Fase>

            {/* 4 · clientes potenciales */}
            <Fase n={4} clave="prospectos" paso={pasos.prospectos}
                  abierta={abierta === "prospectos"} alternar={() => alternar("prospectos")}>
              {(corrida.prospectos || []).length ? (
                <>
                  <div className="pers-lista">
                    {corrida.prospectos.slice(0, CUANTOS_EN_RESUMEN).map((p) => (
                      <div className="pers" key={p.id}>
                        <span className="ini">{p.pais}</span>
                        <span className="info">
                          <b>{p.nombre}</b>
                          <small>{p.sector} · {p.ciudad} · {p.empleados} emp.</small>
                        </span>
                        <Ola nivel={p.nivel} etiquetas={etiquetasOla(corrida)} />
                        <span className="sc tnum">{fmtScore(p.score)}</span>
                      </div>
                    ))}
                  </div>
                  <button className="btn ghost" style={{ marginTop: 12 }}
                          onClick={() => nav("/prospectos")}>
                    {t("common.ver_todos")} ({corrida.prospectos.length}) →
                  </button>
                </>
              ) : <Vacio texto={t("common.cargando")} />}
            </Fase>

            {/* 5 · decisores */}
            <Fase n={5} clave="decisores" paso={pasos.decisores}
                  abierta={abierta === "decisores"} alternar={() => alternar("decisores")}>
              {(corrida.decisores || []).length ? (
                <>
                  <div className="pers-lista">
                    {corrida.decisores.slice(0, CUANTOS_EN_RESUMEN).map((d) => (
                      <div className="pers" key={d.id}>
                        <span className="ini">
                          {d.nombre.split(" ").map((x) => x[0]).slice(0, 2).join("")}
                        </span>
                        <span className="info">
                          <b>{d.nombre}</b>
                          <small>{d.cargo} · {d.empresa}</small>
                        </span>
                        <Idioma codigo={d.idioma} />
                        <span className="sc tnum">{fmtScore(d.score)}</span>
                      </div>
                    ))}
                  </div>
                  <button className="btn ghost" style={{ marginTop: 12 }}
                          onClick={() => nav("/decisores")}>
                    {t("common.ver_todos")} ({corrida.decisores.length}) →
                  </button>
                </>
              ) : <Vacio texto={t("common.cargando")} />}
            </Fase>

            {/* 6 · correos */}
            <Fase n={6} clave="emails" paso={pasos.emails}
                  abierta={abierta === "emails"} alternar={() => alternar("emails")}>
              {(corrida.emails || []).length ? (
                <>
                  {corrida.emails.slice(0, 2).map((e) => (
                    <div className="mail" key={e.id}>
                      <div className="cab">
                        <span className="asunto">{e.asunto}</span>
                        <Idioma codigo={e.idioma} />
                      </div>
                      <pre>{e.cuerpo}</pre>
                    </div>
                  ))}
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
                    <button className="btn ghost" onClick={() => nav("/correos")}>
                      {t("common.ver_todos")} ({corrida.emails.length}) →
                    </button>
                    <button className="btn ghost"
                            onClick={() => descargar("/api/exportar/csv", `${corrida.dominio}.csv`, corrida)}>
                      {t("common.exportar_csv")}
                    </button>
                    <button className="btn ghost"
                            onClick={() => descargar("/api/exportar/xlsx", `${corrida.dominio}.xlsx`, corrida)}>
                      {t("common.exportar_xlsx")}
                    </button>
                  </div>
                </>
              ) : <Vacio texto={t("common.cargando")} />}
            </Fase>
          </div>
        </>
      ) : null}
    </>
  );
}

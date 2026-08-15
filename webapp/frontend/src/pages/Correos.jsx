import React, { useRef, useState } from "react";
import { agregarEnvio, api, descargar, getEmail, getLinkedIn, getSmtp, getX, urlSegura } from "../api.js";
import { Copiar, Idioma, Vacio } from "../componentes/Comunes.jsx";
import { Icono } from "../componentes/Iconos.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { t } from "../i18n/index.js";

const PESTANAS = [
  { id: "texto", clave: "correos.texto" },
  { id: "html", clave: "correos.html" },
  { id: "linkedin", clave: "correos.linkedin" },
];

/** Abre el HTML del correo en una pestaña nueva, sin servidor de por medio. */
function abrirHtml(html) {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  // El objeto queda vivo hasta que la pestaña nueva termina de leerlo; medio
  // minuto alcanza de sobra y evita dejar blobs colgados en memoria.
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

/** Abre el composer de X con el mensaje ya escrito (no hay API abierta que
 *  publique sola; el intent deja todo listo para tocar «Post»). */
function abrirX(correo) {
  const enlace = correo.landing_url || correo.video_url || "";
  const texto = `${correo.linkedin_nota || correo.linkedin || ""}`.slice(0, 240)
    + (enlace ? `\n${enlace}` : "");
  window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(texto)}`,
    "_blank", "noopener");
}

/** Copia el mensaje y abre LinkedIn (la búsqueda del decisor si existe).
 *  LinkedIn no permite pre-cargar mensajes desde afuera: copiar + pegar es
 *  el camino real, y acá queda a un click. */
async function abrirLinkedIn(correo, decisor) {
  try {
    await navigator.clipboard.writeText(correo.linkedin || "");
  } catch {
    /* sin permiso de portapapeles se abre igual */
  }
  // El perfil sale de rastrear un sitio ajeno: se valida el esquema antes de
  // abrirlo. En la app de PC este `window.open` termina en el manejador de
  // URIs del sistema operativo (electron/main.js), así que un `file://` o un
  // `ms-msdt:` acá no sería sólo una pestaña rara.
  window.open(urlSegura(decisor?.linkedin) || "https://www.linkedin.com/messaging/",
    "_blank", "noopener");
}

function Enlaces({ correo }) {
  if (!correo.landing_url && !correo.video_url) return null;
  return (
    <p className="enlaces-msg">
      {correo.video_url ? (
        <a className="con-ico" href={urlSegura(correo.video_url)} target="_blank" rel="noreferrer">
          <Icono nombre="reproducir" tam={15} /> {t("correos.video")}
        </a>
      ) : (
        <span className="apagado">{t("correos.sin_video")}</span>
      )}
      {correo.landing_url ? (
        <a className="con-ico" href={urlSegura(correo.landing_url)} target="_blank" rel="noreferrer">
          <Icono nombre="globo" tam={15} /> {t("correos.web")}
        </a>
      ) : null}
    </p>
  );
}

function Mensaje({ correo, decisor, para, setPara, enviar, estado, smtpListo }) {
  const [pestana, setPestana] = useState("texto");
  const [seguimiento, setSeguimiento] = useState(false);
  const sintetico = Boolean(decisor?.sintetico);

  return (
    <article className="mail">
      <div className="cab">
        <span className="asunto">{correo.asunto}</span>
        <Idioma codigo={correo.idioma} />
        <span className="para">{correo.para || t("correos.sin_destinatario")}</span>
      </div>

      <div className="pestanas">
        {PESTANAS.map((p) => (
          <button key={p.id}
                  className={"pest" + (pestana === p.id ? " on" : "")}
                  onClick={() => setPestana(p.id)}>
            {t(p.clave)}
          </button>
        ))}
      </div>

      {pestana === "texto" ? (
        <>
          <pre>{correo.cuerpo}</pre>
          <div className="acciones">
            <Copiar texto={`${correo.asunto}\n\n${correo.cuerpo}`} />
            <button className="btn ghost con-ico" onClick={() => setSeguimiento(!seguimiento)}
                    aria-expanded={seguimiento}>
              {t("correos.seguimiento")}
              <Icono nombre="chevron" tam={15}
                     className={seguimiento ? "girado" : ""} />
            </button>
          </div>
          {seguimiento ? (
            <>
              <pre className="sep">{correo.seguimiento}</pre>
              <div className="acciones"><Copiar texto={correo.seguimiento} /></div>
            </>
          ) : null}
        </>
      ) : null}

      {pestana === "html" ? (
        <>
          {/* El correo se previsualiza dentro de un iframe aislado: es HTML de
              cliente de correo (tablas, estilos en línea) y meterlo en el DOM
              de la app le pisaría los estilos a las dos partes.

              `sandbox=""` (vacío, o sea TODO denegado) no es decorativo: un
              documento cargado por `srcDoc` hereda el origen del padre, así
              que sin esto un `<script>` que se colara en el cuerpo del correo
              correría con acceso al localStorage de la app — donde viven la
              clave SMTP, la del modelo y las de X y LinkedIn. El HTML del
              correo lo redacta un modelo y lleva datos de sitios ajenos: no
              es contenido propio. Un correo es tablas y estilos en línea
              (Outlook no soporta más que eso), así que negar scripts no le
              saca nada a la vista previa. */}
          <iframe className="vista-html" sandbox="" title={correo.asunto}
                  srcDoc={correo.cuerpo_html} />
          <div className="acciones">
            <Copiar texto={correo.cuerpo_html} etiqueta={t("correos.copiar_html")} />
            <button className="btn ghost con-ico" onClick={() => abrirHtml(correo.cuerpo_html)}>
              {t("correos.abrir_html")}
              <Icono nombre="enlace_externo" tam={15} />
            </button>
          </div>
        </>
      ) : null}

      {pestana === "linkedin" ? (
        <>
          <h4 className="sub">{t("correos.mensaje_linkedin")}</h4>
          <pre>{correo.linkedin}</pre>
          <div className="acciones"><Copiar texto={correo.linkedin} /></div>
          <h4 className="sub">
            {t("correos.nota_linkedin")}{" "}
            <span className="apagado">
              · {t("correos.caracteres", { n: (correo.linkedin_nota || "").length })} / 300
            </span>
          </h4>
          <pre>{correo.linkedin_nota}</pre>
          <div className="acciones"><Copiar texto={correo.linkedin_nota} /></div>
        </>
      ) : null}

      {/* ---- envío real ---- */}
      <div className="acciones" style={{ alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <input type="email" value={para} placeholder={t("correos.destinatario")}
               style={{ minWidth: 220, flex: "1 1 220px" }}
               autoCapitalize="none" autoCorrect="off"
               onChange={(e) => setPara(e.target.value.trim())} />
        <button className="btn" disabled={!smtpListo || !para || estado === "enviando"}
                title={smtpListo ? "" : t("correos.smtp_falta")}
                onClick={() => enviar(correo, para)}>
          {estado === "enviando" ? t("correos.enviando") : t("correos.enviar")}
        </button>
        <button className="btn ghost" onClick={() => abrirLinkedIn(correo, decisor)}>
          {t("correos.abrir_linkedin")}
        </button>
        <button className="btn ghost" onClick={() => abrirX(correo)}>
          {t("correos.abrir_x")}
        </button>
      </div>
      {sintetico && para === correo.para ? (
        <p className="nota" style={{ marginTop: 4 }}>{t("correos.destino_sintetico")}</p>
      ) : null}
      {estado && estado !== "enviando" ? (
        <p className={estado === "ok" ? "nota" : "error-note"}
           style={estado === "ok" ? { color: "var(--green-deep)" } : {}}>
          {estado === "ok" ? t("correos.enviado") : estado}
        </p>
      ) : null}

      <Enlaces correo={correo} />
    </article>
  );
}

/**
 * La tarjeta «Automatizar flujo»: el usuario YA revisó el flujo, los clientes
 * y los canales; un click manda todo y el comprobante llega a su casilla.
 * Automatiza lo que tiene API real (correo por SMTP, post en X con las claves
 * del usuario); LinkedIn, Instagram y TikTok no venden API de envío, así que
 * quedan como cola manual y el comprobante lo dice — acá no se simula nada.
 */
function Automatizar({ listos, adjunto, smtp, correoDe, corrida }) {
  const x = getX();
  const li = getLinkedIn();
  const [conX, setConX] = useState(Boolean(x));
  const [conLi, setConLi] = useState(Boolean(li));
  const [xTexto, setXTexto] = useState("");
  const [comprobanteA, setComprobanteA] = useState(getEmail() || smtp?.usuario || "");
  const [estado, setEstado] = useState("");        // "" | "corriendo" | "listo" | error
  const [comp, setComp] = useState(null);

  // Sólo van por LinkedIn los decisores con identificador de perfil REAL: los
  // sintéticos de la demo no existen, y una llamada al proveedor se paga.
  const paraLinkedIn = listos
    .map(({ correo, decisor }) => ({ correo, decisor }))
    // Sólo perfiles PERSONALES (/in/…): las fichas traen a veces la búsqueda
    // de gente de una empresa, que no identifica a nadie.
    .filter(({ correo, decisor }) =>
      correo.linkedin && /linkedin\.com\/in\//i.test(decisor?.linkedin || ""))
    .map(({ correo, decisor }) => ({
      destinatario: decisor.linkedin,
      texto: correo.linkedin,
      etiqueta: `${decisor.nombre} · ${decisor.empresa}`,
    }));
  const manuales = { instagram: 1, tiktok: 1 };
  if (!conLi || !li) manuales.linkedin = listos.filter((f) => f.correo.linkedin).length;

  const correr = async () => {
    if (!window.confirm(t("auto.confirmar", { n: listos.length }))) return;
    setEstado("corriendo");
    setComp(null);
    try {
      const cuerpo = {
        smtp: { host: smtp.host, puerto: smtp.puerto, usuario: smtp.usuario,
                clave: smtp.clave, ssl: Boolean(smtp.ssl) },
        remitente: smtp.remitente || "",
        correos: listos.map(({ correo, para }) => correoDe(correo, para)),
        adjuntos: adjunto ? [adjunto] : [],
        comprobante_a: comprobanteA.trim(),
        manuales,
        ...(conX && x && xTexto.trim() ? { x, x_texto: xTexto.trim() } : {}),
        ...(conLi && li && paraLinkedIn.length
          ? { linkedin: li, linkedin_mensajes: paraLinkedIn } : {}),
      };
      const r = await api("/api/automatizar", { metodo: "POST", cuerpo });
      setComp(r);
      setEstado("listo");
      // Al panel de métricas: qué se mandó, cuándo y cómo salió.
      agregarEnvio({
        fecha: new Date().toISOString(),
        dominio: corrida?.dominio || "",
        corrida_id: corrida?.id || "",
        correos: { total: r.correos.total, enviados: r.correos.enviados },
        x: r.x ? { ok: r.x.ok, id: r.x.id, url: r.x.url, texto: xTexto.trim() } : null,
        linkedin: r.linkedin
          ? { total: r.linkedin.total, enviados: r.linkedin.enviados,
              proveedor: r.linkedin.proveedor }
          : null,
        manuales: r.manuales || {},
      });
    } catch (e) {
      setEstado(e.message);
    }
  };

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <h3 className="con-ico"><Icono nombre="rayo" tam={17} /> {t("auto.titulo")}</h3>
      <p className="nota" style={{ marginTop: 0 }}>{t("auto.ayuda")}</p>

      {/* `list-style:none` + el icono de cada canal como viñeta: el punto del
          <li> al lado de un icono se leía como suciedad. */}
      <ul className="canales">
        <li>
          <Icono nombre="sobre" tam={16} />
          <span>{t("auto.linea_correos", { n: listos.length })}</span>
        </li>
        <li>
          <label>
            <input type="checkbox" checked={conX} disabled={!x}
                   onChange={(e) => setConX(e.target.checked)} />
            <Icono nombre="equis" tam={16} />
            <span>{x ? t("auto.linea_x") : t("auto.x_faltan_claves")}</span>
          </label>
        </li>
        <li>
          <label>
            <input type="checkbox" checked={conLi} disabled={!li}
                   onChange={(e) => setConLi(e.target.checked)} />
            <Icono nombre="maletin" tam={16} />
            <span>{li
              ? t("auto.linea_li", { n: paraLinkedIn.length, prov: li.proveedor })
              : t("auto.li_falta_proveedor")}</span>
          </label>
        </li>
        <li>
          <Icono nombre="camara" tam={16} />
          <span>
            Instagram · <Icono nombre="musica" tam={16} /> TikTok — {t("auto.linea_manuales")}
          </span>
        </li>
      </ul>

      {conX && x ? (
        <div className="campo crece" style={{ marginBottom: 10 }}>
          <label htmlFor="auto-x">{t("auto.x_texto")}</label>
          <textarea id="auto-x" rows={3} maxLength={280} value={xTexto}
                    onChange={(e) => setXTexto(e.target.value)} />
        </div>
      ) : null}
      <div className="campo crece" style={{ marginBottom: 12 }}>
        <label htmlFor="auto-comp">{t("auto.comprobante_a")}</label>
        <input id="auto-comp" type="email" value={comprobanteA}
               onChange={(e) => setComprobanteA(e.target.value)} />
      </div>

      <button className="btn" disabled={!smtp || !listos.length || estado === "corriendo"}
              title={smtp ? "" : t("correos.smtp_falta")} onClick={correr}>
        {estado === "corriendo" ? t("auto.corriendo") : `${t("auto.boton")} (${listos.length})`}
      </button>

      {estado && estado !== "corriendo" && estado !== "listo" ? (
        <p className="error-note">{estado}</p>
      ) : null}
      {comp ? (
        <div className="comprobante">
          <p style={{ color: "var(--green-deep)", fontWeight: 700 }}>
            <Icono nombre="chequeo_circulo" tam={16} />
            <span>{t("auto.listo_correos", {
              ok: comp.correos.enviados, total: comp.correos.total })}</span>
          </p>
          {comp.linkedin ? (
            <p style={{ color: comp.linkedin.enviados ? "var(--green-deep)" : "" }}>
              <Icono nombre={comp.linkedin.enviados ? "chequeo_circulo" : "equis_circulo"} tam={16} />
              <span>LinkedIn: {t("auto.listo_li", { ok: comp.linkedin.enviados,
                                                    total: comp.linkedin.total,
                                                    prov: comp.linkedin.proveedor })}</span>
            </p>
          ) : null}
          {comp.x ? (
            comp.x.ok
              ? <p>
                  <Icono nombre="chequeo_circulo" tam={16} />
                  <span>{t("auto.listo_x")}{" "}
                    <a href={urlSegura(comp.x.url)} target="_blank" rel="noreferrer">{comp.x.url}</a>
                  </span>
                </p>
              : <p className="error-note">
                  <Icono nombre="equis_circulo" tam={16} />
                  <span>X: {comp.x.detalle}</span>
                </p>
          ) : null}
          {Object.entries(comp.manuales || {}).map(([canal, n]) => (
            <p key={canal} style={{ color: "var(--muted)" }}>
              <Icono nombre="arena" tam={16} />
              <span>{canal[0].toUpperCase() + canal.slice(1)}: {n} {t("auto.pendiente_manual")}</span>
            </p>
          ))}
          <p className={comp.comprobante?.ok ? "" : "error-note"}>
            <Icono nombre={comp.comprobante?.ok ? "chequeo_circulo" : "alerta"} tam={16} />
            <span>{comp.comprobante?.ok
              ? t("auto.comprobante_ok", { a: comp.comprobante.a })
              : t("auto.comprobante_fallo")}</span>
          </p>
        </div>
      ) : null}
    </div>
  );
}

export default function Correos() {
  const { corrida } = useCorrida(getCorridaId());
  const [idioma, setIdioma] = useState("");
  const [paras, setParas] = useState({});
  const [estados, setEstados] = useState({});
  const [adjunto, setAdjunto] = useState(null);
  const [avisoLote, setAvisoLote] = useState("");
  const refArchivo = useRef(null);
  const smtp = getSmtp();

  if (!corrida) return <Vacio />;

  const todos = corrida.emails || [];
  const filas = idioma ? todos.filter((e) => e.idioma === idioma) : todos;
  const porIdioma = todos.reduce((a, e) => ({ ...a, [e.idioma]: (a[e.idioma] || 0) + 1 }), {});
  const decisores = Object.fromEntries((corrida.decisores || []).map((d) => [d.id, d]));
  const paraDe = (e) => (paras[e.id] !== undefined ? paras[e.id] : e.para);

  const elegirAdjunto = (e) => {
    const archivo = e.target.files?.[0];
    if (!archivo) return setAdjunto(null);
    if (archivo.size > 5 * 1024 * 1024) {
      setAvisoLote(t("correos.adjunto_grande"));
      e.target.value = "";
      return;
    }
    const lector = new FileReader();
    lector.onload = () => setAdjunto({
      nombre: archivo.name,
      tipo: archivo.type || "application/octet-stream",
      contenido_b64: String(lector.result).split(",", 2)[1] || "",
    });
    lector.readAsDataURL(archivo);
  };

  const enviarVarios = async (correos) => {
    const cuerpo = {
      smtp: { host: smtp.host, puerto: smtp.puerto, usuario: smtp.usuario,
              clave: smtp.clave, ssl: Boolean(smtp.ssl) },
      remitente: smtp.remitente || "",
      correos: correos.map(({ correo, para }) => ({
        para, asunto: correo.asunto, cuerpo: correo.cuerpo,
        cuerpo_html: correo.cuerpo_html || "",
      })),
      adjuntos: adjunto ? [adjunto] : [],
    };
    const r = await api("/api/enviar", { metodo: "POST", cuerpo });
    const porPara = Object.fromEntries(r.resultados.map((x) => [x.para, x]));
    setEstados((prev) => {
      const nuevo = { ...prev };
      for (const { correo, para } of correos) {
        const res = porPara[para];
        nuevo[correo.id] = res?.ok ? "ok" : (res?.detalle || "error");
      }
      return nuevo;
    });
    return r;
  };

  const enviarUno = async (correo, para) => {
    setEstados((prev) => ({ ...prev, [correo.id]: "enviando" }));
    try {
      await enviarVarios([{ correo, para }]);
    } catch (e) {
      setEstados((prev) => ({ ...prev, [correo.id]: e.message }));
    }
  };

  // Al lote entran sólo los correos con destinatario REAL: los sintéticos de
  // la demo tienen casillas fabricadas y mandarles ahí es rebote seguro.
  const listos = filas
    .map((e) => ({ correo: e, para: paraDe(e), decisor: decisores[e.decisor_id] }))
    .filter(({ para, decisor, correo }) =>
      para && (!decisor?.sintetico || para !== correo.para));

  const enviarLote = async () => {
    setAvisoLote(t("correos.enviando"));
    try {
      const r = await enviarVarios(listos);
      setAvisoLote(`${t("correos.enviado")}: ${r.enviados}/${listos.length}`);
    } catch (e) {
      setAvisoLote(e.message);
    }
  };

  return (
    <>
      <h1 className="page-title">{t("correos.titulo")}</h1>
      <p className="page-sub">{t("correos.subtitulo")}</p>

      <div className="toolbar" style={{ flexWrap: "wrap" }}>
        <select value={idioma} onChange={(e) => setIdioma(e.target.value)}>
          <option value="">{t("correos.todos")} ({todos.length})</option>
          {["es", "pt", "en"].filter((i) => porIdioma[i]).map((i) => (
            <option key={i} value={i}>{i.toUpperCase()} ({porIdioma[i]})</option>
          ))}
        </select>
        <button className="btn ghost con-ico"
                onClick={() => descargar("/api/exportar/csv", `${corrida.dominio}.csv`, corrida)}>
          <Icono nombre="descargar" tam={15} /> {t("common.exportar_csv")}
        </button>
        <button className="btn ghost con-ico"
                onClick={() => descargar("/api/exportar/xlsx", `${corrida.dominio}.xlsx`, corrida)}>
          <Icono nombre="descargar" tam={15} /> {t("common.exportar_xlsx")}
        </button>
        <button className="btn ghost con-ico" onClick={() => refArchivo.current?.click()}>
          <Icono nombre="clip" tam={15} />
          {adjunto ? adjunto.nombre : t("correos.adjuntar")}
        </button>
        <input ref={refArchivo} type="file" style={{ display: "none" }}
               onChange={elegirAdjunto} />
        <button className="btn" disabled={!smtp || !listos.length}
                title={smtp ? "" : t("correos.smtp_falta")}
                onClick={enviarLote}>
          {t("correos.enviar_todos")} ({listos.length})
        </button>
      </div>
      {!smtp ? <p className="nota">{t("correos.smtp_falta")}</p> : null}
      {avisoLote ? <p className="nota">{avisoLote}</p> : null}

      <Automatizar listos={listos} adjunto={adjunto} smtp={smtp} corrida={corrida}
                   correoDe={(correo, para) => ({
                     para, asunto: correo.asunto, cuerpo: correo.cuerpo,
                     cuerpo_html: correo.cuerpo_html || "",
                   })} />

      {filas.length ? filas.map((e) => (
        <Mensaje key={e.id} correo={e} decisor={decisores[e.decisor_id]}
                 para={paraDe(e)}
                 setPara={(v) => setParas((prev) => ({ ...prev, [e.id]: v }))}
                 enviar={enviarUno} estado={estados[e.id]}
                 smtpListo={Boolean(smtp)} />
      )) : <Vacio />}
    </>
  );
}

import React, { useEffect, useState } from "react";
import {
  api, esNativo, getBase, getClaveIA, getEndpointIA, getModeloIA, getModelosActualizado,
  getModelosDisponibles, getOwner, getProveedorIA, activarLicencia, getLicencia,
  getLinkedIn, getSmtp, getX, listarModelosIA, PROVEEDORES_CON_LISTA_DE_MODELOS,
  setBase, setClaveIA, setEndpointIA, setLinkedIn, setModeloIA, setModelosDisponibles,
  setOwner, setProveedorIA, setSmtp, setToken, setX,
} from "../api.js";
import { SelectorIdioma } from "../App.jsx";
import { Aviso } from "../componentes/Comunes.jsx";
import { Icono } from "../componentes/Iconos.jsx";
import { t } from "../i18n/index.js";

/**
 * Licencia del programa instalado. En la web no se muestra: ahí el límite es
 * el cupo gratis, que ya tiene su propio cartel en Explorar.
 */
function FormLicencia() {
  const [lic, setLic] = useState(null);
  const [clave, setClave] = useState("");
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { getLicencia().then(setLic); }, []);
  if (!lic || !lic.aplica) return null;

  const activar = async (e) => {
    e.preventDefault();
    setError(""); setAviso("");
    try {
      const r = await activarLicencia(clave.trim());
      setLic({ aplica: true, ...r });
      setClave("");
      setAviso(t("config.lic_activada"));
      setTimeout(() => setAviso(""), 3000);
    } catch (err) {
      setError(err.message);
    }
  };

  const EDICION = { demo: t("config.lic_demo"), cliente: t("config.lic_cliente"),
                    owner: t("config.lic_owner") };
  return (
    <form className="card" style={{ maxWidth: 620, marginBottom: 14 }} onSubmit={activar}>
      <h3>{t("config.lic")}</h3>
      <p style={{ margin: "0 0 10px", fontSize: 14 }}>
        <b className="con-ico" style={{ color: lic.activa ? "var(--green-deep)" : "var(--amber)" }}>
          <Icono nombre={lic.activa ? "escudo" : "alerta"} tam={16} />
          {EDICION[lic.edicion] || lic.edicion}
        </b>
        {lic.dias_restantes > 0 ? (
          <span className="apagado">
            {" "}· {t("config.lic_dias", { n: lic.dias_restantes })}
          </span>
        ) : null}
        {lic.email ? <span className="apagado"> · {lic.email}</span> : null}
      </p>
      {lic.motivo ? <Aviso>{lic.motivo}</Aviso> : null}

      {/* La edición owner no tiene nada que activar. */}
      {lic.edicion === "owner" ? (
        <p className="nota" style={{ marginBottom: 0 }}>{t("config.lic_owner_nota")}</p>
      ) : (
        <>
          <div className="campo crece" style={{ margin: "10px 0" }}>
            <label htmlFor="lic-clave">{t("config.lic_clave")}</label>
            <input id="lic-clave" type="text" value={clave} autoCapitalize="none"
                   autoCorrect="off" placeholder="eyJlbWFpbCI6…"
                   onChange={(e) => setClave(e.target.value)} />
          </div>
          <button className="btn" type="submit" disabled={!clave.trim()}>
            {t("config.lic_activar")}
          </button>
          <p className="nota">{t("config.lic_ayuda")}</p>
        </>
      )}
      {aviso ? <p className="nota" style={{ color: "var(--green-deep)" }}>{aviso}</p> : null}
      {error ? <p className="error-note">{error}</p> : null}
    </form>
  );
}

function FormSmtp() {
  const guardado = getSmtp() || {};
  const [smtp, setSmtpLocal] = useState({
    host: guardado.host || "", puerto: guardado.puerto || 587,
    usuario: guardado.usuario || "", clave: guardado.clave || "",
    ssl: Boolean(guardado.ssl), remitente: guardado.remitente || "",
  });
  const [aviso, setAviso] = useState("");

  const campo = (clave, valor) => setSmtpLocal({ ...smtp, [clave]: valor });
  const guardarSmtp = (e) => {
    e.preventDefault();
    setSmtp(smtp.host && smtp.usuario ? smtp : null);
    setAviso(smtp.host ? t("config.smtp_guardado") : t("config.clave_borrada"));
    setTimeout(() => setAviso(""), 2500);
  };

  return (
    <form className="card" style={{ maxWidth: 620, marginBottom: 14 }} onSubmit={guardarSmtp}>
      <h3>{t("config.smtp")}</h3>
      <p className="nota" style={{ marginTop: 0 }}>{t("config.smtp_ayuda")}</p>
      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "2fr 1fr" }}>
        <div className="campo">
          <label htmlFor="smtp-host">{t("config.smtp_host")}</label>
          <input id="smtp-host" type="text" value={smtp.host} placeholder="smtp.gmail.com"
                 autoCapitalize="none" autoCorrect="off"
                 onChange={(e) => campo("host", e.target.value.trim())} />
        </div>
        <div className="campo">
          <label htmlFor="smtp-puerto">{t("config.smtp_puerto")}</label>
          <input id="smtp-puerto" type="number" value={smtp.puerto} min="1" max="65535"
                 onChange={(e) => campo("puerto", Number(e.target.value) || 587)} />
        </div>
      </div>
      <div className="campo crece" style={{ margin: "10px 0" }}>
        <label htmlFor="smtp-usuario">{t("config.smtp_usuario")}</label>
        <input id="smtp-usuario" type="email" value={smtp.usuario}
               placeholder="vos@tuempresa.com" autoCapitalize="none"
               onChange={(e) => campo("usuario", e.target.value.trim())} />
      </div>
      <div className="campo crece" style={{ marginBottom: 10 }}>
        <label htmlFor="smtp-clave">{t("config.smtp_clave")}</label>
        <input id="smtp-clave" type="password" value={smtp.clave}
               autoComplete="off"
               onChange={(e) => campo("clave", e.target.value)} />
      </div>
      <div className="campo crece" style={{ marginBottom: 10 }}>
        <label htmlFor="smtp-remitente">{t("config.smtp_remitente")}</label>
        <input id="smtp-remitente" type="text" value={smtp.remitente}
               onChange={(e) => campo("remitente", e.target.value)} />
      </div>
      <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13.5 }}>
        <input type="checkbox" checked={smtp.ssl}
               onChange={(e) => campo("ssl", e.target.checked)} />
        {t("config.smtp_ssl")}
      </label>
      <div style={{ marginTop: 12 }}>
        <button className="btn" type="submit">{t("config.guardar")}</button>
      </div>
      {aviso ? <p className="nota" style={{ color: "var(--green-deep)" }}>{aviso}</p> : null}
    </form>
  );
}

function FormLinkedIn() {
  const guardado = getLinkedIn() || {};
  const [li, setLiLocal] = useState({
    proveedor: guardado.proveedor || "unipile",
    dsn: guardado.dsn || "", api_key: guardado.api_key || "",
    account_id: guardado.account_id || "",
  });
  const [aviso, setAviso] = useState("");
  const campo = (clave, valor) => setLiLocal({ ...li, [clave]: valor.trim() });
  const guardarLi = (e) => {
    e.preventDefault();
    setLinkedIn(li.dsn && li.api_key && li.account_id ? li : null);
    setAviso(li.dsn ? t("config.li_guardado") : t("config.clave_borrada"));
    setTimeout(() => setAviso(""), 2500);
  };
  return (
    <form className="card" style={{ maxWidth: 620, marginBottom: 14 }} onSubmit={guardarLi}>
      <h3>{t("config.li")}</h3>
      <p className="nota" style={{ marginTop: 0 }}>{t("config.li_ayuda")}</p>
      {/* El riesgo se dice ANTES de que pegue la clave, no después de que le
          restrinjan la cuenta. */}
      <Aviso>{t("config.li_riesgo")}</Aviso>
      <div className="campo crece" style={{ margin: "10px 0" }}>
        <label htmlFor="li-proveedor">{t("config.li_proveedor")}</label>
        <select id="li-proveedor" value={li.proveedor}
                onChange={(e) => campo("proveedor", e.target.value)}>
          <option value="unipile">Unipile</option>
        </select>
      </div>
      <div className="campo crece" style={{ marginBottom: 10 }}>
        <label htmlFor="li-dsn">{t("config.li_dsn")}</label>
        <input id="li-dsn" type="text" value={li.dsn} autoCapitalize="none"
               placeholder="api1.unipile.com:13111"
               onChange={(e) => campo("dsn", e.target.value)} />
      </div>
      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr" }}>
        <div className="campo">
          <label htmlFor="li-key">{t("config.li_key")}</label>
          <input id="li-key" type="password" value={li.api_key} autoComplete="off"
                 onChange={(e) => campo("api_key", e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="li-cuenta">{t("config.li_cuenta")}</label>
          <input id="li-cuenta" type="text" value={li.account_id} autoCapitalize="none"
                 onChange={(e) => campo("account_id", e.target.value)} />
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <button className="btn" type="submit">{t("config.guardar")}</button>
      </div>
      {aviso ? <p className="nota" style={{ color: "var(--green-deep)" }}>{aviso}</p> : null}
    </form>
  );
}

function FormX() {
  const guardado = getX() || {};
  const [x, setXLocal] = useState({
    consumer_key: guardado.consumer_key || "",
    consumer_secret: guardado.consumer_secret || "",
    access_token: guardado.access_token || "",
    access_secret: guardado.access_secret || "",
  });
  const [aviso, setAviso] = useState("");
  const campo = (clave, valor) => setXLocal({ ...x, [clave]: valor.trim() });
  const guardarX = (e) => {
    e.preventDefault();
    setX(x.consumer_key && x.access_token ? x : null);
    setAviso(x.consumer_key ? t("config.x_guardado") : t("config.clave_borrada"));
    setTimeout(() => setAviso(""), 2500);
  };
  const CAMPOS = [
    ["consumer_key", "API Key"], ["consumer_secret", "API Key Secret"],
    ["access_token", "Access Token"], ["access_secret", "Access Token Secret"],
  ];
  return (
    <form className="card" style={{ maxWidth: 620, marginBottom: 14 }} onSubmit={guardarX}>
      <h3>{t("config.x")}</h3>
      <p className="nota" style={{ marginTop: 0 }}>{t("config.x_ayuda")}</p>
      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr" }}>
        {CAMPOS.map(([clave, etiqueta]) => (
          <div className="campo" key={clave}>
            <label htmlFor={`x-${clave}`}>{etiqueta}</label>
            <input id={`x-${clave}`} type="password" value={x[clave]}
                   autoComplete="off" autoCapitalize="none"
                   onChange={(e) => campo(clave, e.target.value)} />
          </div>
        ))}
      </div>
      <div style={{ marginTop: 12 }}>
        <button className="btn" type="submit">{t("config.guardar")}</button>
      </div>
      {aviso ? <p className="nota" style={{ color: "var(--green-deep)" }}>{aviso}</p> : null}
    </form>
  );
}

export default function Configuracion({ onSalir }) {
  const [base, setBaseLocal] = useState(getBase());
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [clave, setClaveLocal] = useState(getClaveIA());
  const [verClave, setVerClave] = useState(false);
  const [avisoClave, setAvisoClave] = useState("");
  const [owner, setOwnerLocal] = useState(getOwner());
  const [proveedor, setProveedorLocal] = useState(getProveedorIA());
  const [endpoint, setEndpointLocal] = useState(getEndpointIA());
  // El modelo puntual dentro del proveedor (regula el consumo de tokens de
  // ESTE cliente) y la última lista que trajo el botón «Actualizar» — una
  // caché por proveedor, para no perderla al ir y volver del selector.
  const [modelo, setModeloLocal] = useState(getModeloIA(proveedor));
  const [modelos, setModelosLocal] = useState(getModelosDisponibles(proveedor));
  const [actualizadoModelos, setActualizadoModelos] = useState(getModelosActualizado(proveedor));
  const [actualizandoModelos, setActualizandoModelos] = useState(false);
  const [errorModelos, setErrorModelos] = useState("");
  const hayListaModelos = PROVEEDORES_CON_LISTA_DE_MODELOS.includes(proveedor);

  // Al cambiar de proveedor se muestra LO SUYO: su modelo elegido y su
  // última lista traída, no lo que quedó puesto del proveedor anterior.
  const elegirProveedor = (p) => {
    setProveedorLocal(p);
    setModeloLocal(getModeloIA(p));
    setModelosLocal(getModelosDisponibles(p));
    setActualizadoModelos(getModelosActualizado(p));
    setErrorModelos("");
  };

  const actualizarModelos = async () => {
    setErrorModelos("");
    setActualizandoModelos(true);
    try {
      const r = await listarModelosIA(proveedor, clave.trim());
      setModelosLocal(r.modelos);
      setModelosDisponibles(proveedor, r.modelos);
      setActualizadoModelos(new Date().toISOString());
      // Si el modelo elegido hasta ahora ya no está en la lista nueva (o
      // todavía no había ninguno), se cae al primero — nunca se manda al
      // servidor un modelo que el proveedor ya no reconoce.
      if (!r.modelos.includes(modelo)) setModeloLocal(r.modelos[0] || "");
    } catch (err) {
      setErrorModelos(err.message);
    } finally {
      setActualizandoModelos(false);
    }
  };

  // El formato de la clave delata al proveedor; mostrar el prefijo esperado
  // evita el clásico "pegué la de OpenAI con Claude elegido".
  const pistaClave = {
    claude: "sk-ant-…", openai: "sk-…", gemini: "AIza…", copilot: "········",
    grok: "xai-…",
  }[proveedor];

  const guardarClave = (e) => {
    e.preventDefault();
    setClaveIA(clave);
    setProveedorIA(proveedor);
    setEndpointIA(proveedor === "copilot" ? endpoint : "");
    setModeloIA(proveedor, modelo);
    // El código de dueño se guarda junto: viaja como encabezado y exime del
    // cupo gratis de la web (se valida en el servidor contra MVCLIENTE_OWNER).
    setOwner(owner);
    setAvisoClave(clave.trim() || owner.trim()
      ? t("config.clave_guardada") : t("config.clave_borrada"));
    setTimeout(() => setAvisoClave(""), 2500);
  };

  const guardar = (e) => {
    e.preventDefault();
    setBase(base);
    setError("");
    setAviso(t("config.guardado"));
    setTimeout(() => setAviso(""), 2000);
  };

  const probar = async () => {
    setAviso("");
    setError("");
    // Se guarda antes de probar: si no, se estaría probando la dirección
    // vieja y el resultado no diría nada sobre la que el usuario escribió.
    setBase(base);
    try {
      const r = await api("/api/salud");
      setAviso(`${t("config.conexion_ok")} · v${r.version}`);
    } catch (e) {
      setError(`${t("config.conexion_error")}: ${e.message}`);
    }
  };

  const salir = () => {
    setToken(null);
    onSalir?.();
    window.location.hash = "#/login";
  };

  return (
    <>
      <h1 className="page-title">{t("config.titulo")}</h1>
      <p className="page-sub">{t("config.subtitulo")}</p>

      <div className="card" style={{ maxWidth: 620, marginBottom: 14 }}>
        <h3>{t("config.idioma")}</h3>
        <div style={{ maxWidth: 220 }}><SelectorIdioma /></div>
      </div>

      <form className="card" style={{ maxWidth: 620, marginBottom: 14 }} onSubmit={guardarClave}>
        <h3>{t("config.clave_ia")}</h3>
        <div className="campo" style={{ maxWidth: 300, marginBottom: 10 }}>
          <label htmlFor="proveedor-ia">{t("config.proveedor")}</label>
          <select id="proveedor-ia" value={proveedor}
                  onChange={(e) => elegirProveedor(e.target.value)}>
            <option value="claude">{t("config.proveedor_claude")}</option>
            <option value="openai">{t("config.proveedor_openai")}</option>
            <option value="gemini">{t("config.proveedor_gemini")}</option>
            <option value="copilot">{t("config.proveedor_copilot")}</option>
            <option value="grok">{t("config.proveedor_grok")}</option>
          </select>
        </div>
        <div className="campo crece" style={{ marginBottom: 10 }}>
          {/* type=password para que no quede a la vista en una demo o una
              captura; el botón de al lado la muestra si hace falta revisarla. */}
          <input type={verClave ? "text" : "password"} value={clave}
                 placeholder={pistaClave} autoCapitalize="none" autoCorrect="off"
                 autoComplete="off" spellCheck="false"
                 onChange={(e) => setClaveLocal(e.target.value)} />
        </div>
        {proveedor === "copilot" ? (
          <>
            <div className="campo crece" style={{ marginBottom: 10 }}>
              <label htmlFor="endpoint-ia">{t("config.endpoint")}</label>
              <input id="endpoint-ia" type="text" value={endpoint}
                     placeholder="https://mi-recurso.openai.azure.com/openai/deployments/…/chat/completions?api-version=…"
                     autoCapitalize="none" autoCorrect="off" inputMode="url"
                     spellCheck="false"
                     onChange={(e) => setEndpointLocal(e.target.value)} />
            </div>
            <p className="nota" style={{ marginTop: 0 }}>{t("config.endpoint_ayuda")}</p>
          </>
        ) : null}
        {/* El modelo puntual: regula el consumo de tokens del cliente sin
            tocar código — Copilot queda afuera porque en Azure el modelo lo
            fija el deployment de la URL, no hay lista que traer. */}
        {hayListaModelos ? (
          <div className="campo crece" style={{ marginBottom: 10 }}>
            <label htmlFor="modelo-ia">{t("config.modelo")}</label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <select id="modelo-ia" value={modelo} style={{ flex: "1 1 220px" }}
                      onChange={(e) => setModeloLocal(e.target.value)}>
                <option value="">{t("config.modelo_default")}</option>
                {modelos.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
              <button className="btn ghost" type="button" onClick={actualizarModelos}
                      disabled={actualizandoModelos || !clave.trim()}>
                {actualizandoModelos ? t("config.modelo_actualizando") : t("config.modelo_actualizar")}
              </button>
            </div>
            <p className="nota" style={{ marginTop: 6 }}>
              {modelos.length ? (
                <>
                  {t("config.modelo_ayuda", { n: modelos.length })}
                  {actualizadoModelos ? (
                    <> {t("config.modelo_actualizado",
                        { fecha: new Date(actualizadoModelos).toLocaleDateString() })}</>
                  ) : null}
                </>
              ) : t("config.modelo_sin_lista")}
            </p>
            {errorModelos ? <p className="error-note">{errorModelos}</p> : null}
          </div>
        ) : null}
        <p className="nota" style={{ marginTop: 0 }}>{t("config.clave_ayuda")}</p>
        <div className="campo crece" style={{ margin: "12px 0 6px" }}>
          <label htmlFor="owner">{t("config.owner")} <i>({t("explorar.opcional")})</i></label>
          <input id="owner" type="password" value={owner}
                 autoCapitalize="none" autoCorrect="off" autoComplete="off"
                 onChange={(e) => setOwnerLocal(e.target.value)} />
        </div>
        <p className="nota" style={{ marginTop: 0 }}>{t("config.owner_ayuda")}</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          <button className="btn" type="submit">{t("config.guardar")}</button>
          <button className="btn ghost" type="button" onClick={() => setVerClave(!verClave)}>
            {verClave ? t("config.clave_ocultar") : t("config.clave_ver")}
          </button>
        </div>
        {avisoClave ? (
          <p className="nota" style={{ color: "var(--green-deep)" }}>{avisoClave}</p>
        ) : null}
      </form>

      <FormLicencia />
      <FormSmtp />
      <FormLinkedIn />
      <FormX />

      <form className="card" style={{ maxWidth: 620 }} onSubmit={guardar}>
        <h3>{t("config.servidor")}</h3>
        <div className="campo crece" style={{ marginBottom: 10 }}>
          <input type="text" value={base} placeholder="http://192.168.1.10:8810"
                 autoCapitalize="none" autoCorrect="off" inputMode="url"
                 onChange={(e) => setBaseLocal(e.target.value)} />
        </div>
        <p className="nota" style={{ marginTop: 0 }}>{t("config.servidor_ayuda")}</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          <button className="btn" type="submit">{t("config.guardar")}</button>
          <button className="btn ghost" type="button" onClick={probar}>{t("config.probar")}</button>
          {!esNativo() ? (
            <button className="btn ghost" type="button" onClick={salir}>{t("config.salir")}</button>
          ) : null}
        </div>
        {aviso ? <p className="nota" style={{ color: "var(--green-deep)" }}>{aviso}</p> : null}
        {error ? <p className="error-note">{error}</p> : null}
      </form>
    </>
  );
}

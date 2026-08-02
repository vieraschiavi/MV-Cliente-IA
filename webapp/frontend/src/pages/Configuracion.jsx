import React, { useState } from "react";
import {
  api, esNativo, getBase, getClaveIA, getEndpointIA, getOwner, getProveedorIA,
  setBase, setClaveIA, setEndpointIA, setOwner, setProveedorIA, setToken,
} from "../api.js";
import { SelectorIdioma } from "../App.jsx";
import { t } from "../i18n/index.js";

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

  // El formato de la clave delata al proveedor; mostrar el prefijo esperado
  // evita el clásico "pegué la de OpenAI con Claude elegido".
  const pistaClave = {
    claude: "sk-ant-…", openai: "sk-…", gemini: "AIza…", copilot: "········",
  }[proveedor];

  const guardarClave = (e) => {
    e.preventDefault();
    setClaveIA(clave);
    setProveedorIA(proveedor);
    setEndpointIA(proveedor === "copilot" ? endpoint : "");
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
                  onChange={(e) => setProveedorLocal(e.target.value)}>
            <option value="claude">{t("config.proveedor_claude")}</option>
            <option value="openai">{t("config.proveedor_openai")}</option>
            <option value="gemini">{t("config.proveedor_gemini")}</option>
            <option value="copilot">{t("config.proveedor_copilot")}</option>
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

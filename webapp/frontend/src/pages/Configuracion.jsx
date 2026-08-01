import React, { useState } from "react";
import { api, esNativo, getBase, setBase, setToken } from "../api.js";
import { SelectorIdioma } from "../App.jsx";
import { t } from "../i18n/index.js";

export default function Configuracion({ onSalir }) {
  const [base, setBaseLocal] = useState(getBase());
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");

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

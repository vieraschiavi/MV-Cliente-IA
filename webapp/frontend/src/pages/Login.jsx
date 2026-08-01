import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api.js";
import { SelectorIdioma } from "../App.jsx";
import { t } from "../i18n/index.js";

export default function Login({ onEntrar }) {
  const nav = useNavigate();
  const [password, setPassword] = useState("");
  const [entrando, setEntrando] = useState(false);
  const [error, setError] = useState("");

  const enviar = async (e) => {
    e.preventDefault();
    setEntrando(true);
    setError("");
    try {
      const r = await api("/api/auth/login", { metodo: "POST", cuerpo: { password } });
      setToken(r.token);
      onEntrar?.();
      nav("/", { replace: true });
    } catch (e2) {
      setError(e2.status === 401 ? t("login.error") : e2.message);
    } finally {
      setEntrando(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <img src="./mv_icon.png" alt={t("common.marca_texto")} />
        <h1 dangerouslySetInnerHTML={{ __html: t("common.marca") }} />
        <p>{t("login.subtitulo")}</p>
        <form onSubmit={enviar}>
          <input type="password" value={password} autoFocus
                 placeholder={t("login.placeholder")}
                 onChange={(e) => setPassword(e.target.value)} />
          <button className="btn" type="submit" disabled={entrando || !password}>
            {entrando ? t("login.entrando") : t("login.entrar")}
          </button>
        </form>
        {error ? <p className="error-note">{error}</p> : null}
        <div style={{ marginTop: 22 }}><SelectorIdioma /></div>
      </div>
    </div>
  );
}

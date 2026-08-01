import React, { useState } from "react";
import { descargar } from "../api.js";
import { Copiar, Idioma, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { t } from "../i18n/index.js";

export default function Correos() {
  const { corrida } = useCorrida(getCorridaId());
  const [idioma, setIdioma] = useState("");
  const [abierto, setAbierto] = useState("");

  if (!corrida) return <Vacio />;

  const todos = corrida.emails || [];
  const filas = idioma ? todos.filter((e) => e.idioma === idioma) : todos;
  const porIdioma = todos.reduce((a, e) => ({ ...a, [e.idioma]: (a[e.idioma] || 0) + 1 }), {});

  return (
    <>
      <h1 className="page-title">{t("correos.titulo")}</h1>
      <p className="page-sub">{t("correos.subtitulo")}</p>

      <div className="toolbar">
        <select value={idioma} onChange={(e) => setIdioma(e.target.value)}>
          <option value="">{t("correos.todos")} ({todos.length})</option>
          {["es", "pt", "en"].filter((i) => porIdioma[i]).map((i) => (
            <option key={i} value={i}>{i.toUpperCase()} ({porIdioma[i]})</option>
          ))}
        </select>
        <button className="btn ghost"
                onClick={() => descargar(`/api/corridas/${corrida.id}/csv`, `${corrida.dominio}.csv`)}>
          {t("common.exportar_csv")}
        </button>
        <button className="btn ghost"
                onClick={() => descargar(`/api/corridas/${corrida.id}/xlsx`, `${corrida.dominio}.xlsx`)}>
          {t("common.exportar_xlsx")}
        </button>
      </div>

      {filas.length ? filas.map((e) => (
        <article className="mail" key={e.id}>
          <div className="cab">
            <span className="asunto">{e.asunto}</span>
            <Idioma codigo={e.idioma} />
            <span style={{ color: "var(--faint)", fontSize: 12.5 }}>{e.para}</span>
          </div>
          <pre>{e.cuerpo}</pre>
          <div className="acciones">
            <Copiar texto={`${e.asunto}\n\n${e.cuerpo}`} />
            <button className="btn ghost"
                    onClick={() => setAbierto(abierto === e.id ? "" : e.id)}>
              {t("correos.seguimiento")} {abierto === e.id ? "▴" : "▾"}
            </button>
          </div>
          {abierto === e.id ? (
            <>
              <pre style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
                {e.seguimiento}
              </pre>
              <div className="acciones"><Copiar texto={e.seguimiento} /></div>
            </>
          ) : null}
        </article>
      )) : <Vacio />}
    </>
  );
}

import React, { useState } from "react";
import { descargar } from "../api.js";
import { Copiar, Idioma, Vacio } from "../componentes/Comunes.jsx";
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

function Enlaces({ correo }) {
  if (!correo.landing_url && !correo.video_url) return null;
  return (
    <p className="enlaces-msg">
      {correo.video_url ? (
        <a href={correo.video_url} target="_blank" rel="noreferrer">▸ {t("correos.video")}</a>
      ) : (
        <span className="apagado">{t("correos.sin_video")}</span>
      )}
      {correo.landing_url ? (
        <a href={correo.landing_url} target="_blank" rel="noreferrer">🔗 {t("correos.web")}</a>
      ) : null}
    </p>
  );
}

function Mensaje({ correo }) {
  const [pestana, setPestana] = useState("texto");
  const [seguimiento, setSeguimiento] = useState(false);

  return (
    <article className="mail">
      <div className="cab">
        <span className="asunto">{correo.asunto}</span>
        <Idioma codigo={correo.idioma} />
        <span className="para">{correo.para}</span>
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
            <button className="btn ghost" onClick={() => setSeguimiento(!seguimiento)}>
              {t("correos.seguimiento")} {seguimiento ? "▴" : "▾"}
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
              de la app le pisaría los estilos a las dos partes. */}
          <iframe className="vista-html" title={correo.asunto} srcDoc={correo.cuerpo_html} />
          <div className="acciones">
            <Copiar texto={correo.cuerpo_html} etiqueta={t("correos.copiar_html")} />
            <button className="btn ghost" onClick={() => abrirHtml(correo.cuerpo_html)}>
              {t("correos.abrir_html")} ↗
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

      <Enlaces correo={correo} />
    </article>
  );
}

export default function Correos() {
  const { corrida } = useCorrida(getCorridaId());
  const [idioma, setIdioma] = useState("");

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

      {filas.length ? filas.map((e) => <Mensaje key={e.id} correo={e} />) : <Vacio />}
    </>
  );
}

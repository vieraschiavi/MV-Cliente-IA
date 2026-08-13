import React, { useState } from "react";
import { api, borrarEnvios, fmtNum, getEnvios, getX, urlSegura } from "../api.js";
import { Aviso, Vacio } from "../componentes/Comunes.jsx";
import { getIdioma, t } from "../i18n/index.js";

/**
 * Panel de métricas por canal y por publicación.
 *
 * El historial de envíos vive en ESTE dispositivo (localStorage), no en el
 * servidor: el despliegue web es serverless y no tiene disco que sobreviva a
 * la respuesta, así que un historial de servidor sencillamente no existiría
 * ahí. Con esto el panel anda igual en la web, en el programa de PC y en el
 * APK — y los datos de contacto de nadie salen del aparato del usuario.
 *
 * Las métricas de X (impresiones, likes, respuestas) sí se piden en vivo:
 * son números que sólo tiene X y cambian con el tiempo.
 */
function Tarjeta({ titulo, valor, pie, color }) {
  return (
    <div className="card" style={{ margin: 0, padding: "14px 16px" }}>
      <p style={{ margin: 0, color: "var(--muted)", fontSize: 12.5, fontWeight: 700 }}>
        {titulo}
      </p>
      <p className="tnum" style={{ margin: "4px 0 0", fontSize: 26, fontWeight: 800,
                                   color: color || "var(--tinta)" }}>
        {valor}
      </p>
      {pie ? <p className="nota" style={{ margin: "2px 0 0" }}>{pie}</p> : null}
    </div>
  );
}

function fecha(iso) {
  try {
    return new Date(iso).toLocaleString(
      { es: "es-UY", pt: "pt-BR", en: "en-US" }[getIdioma()] || "es-UY",
      { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export default function Metricas() {
  const [envios, setEnvios] = useState(getEnvios());
  const [metricas, setMetricas] = useState({});
  const [estado, setEstado] = useState("");
  const x = getX();

  // Los posts de X publicados desde acá: son los que tienen métricas propias.
  const posts = envios.filter((e) => e.x?.ok && e.x.id);

  const totales = envios.reduce((a, e) => ({
    correos: a.correos + (e.correos?.total || 0),
    correos_ok: a.correos_ok + (e.correos?.enviados || 0),
    li: a.li + (e.linkedin?.total || 0),
    li_ok: a.li_ok + (e.linkedin?.enviados || 0),
    posts: a.posts + (e.x?.ok ? 1 : 0),
  }), { correos: 0, correos_ok: 0, li: 0, li_ok: 0, posts: 0 });

  const sumaX = posts.reduce((a, e) => {
    const m = metricas[e.x.id];
    if (!m?.ok) return a;
    return {
      impresiones: a.impresiones + m.impresiones,
      likes: a.likes + m.likes,
      respuestas: a.respuestas + m.respuestas,
    };
  }, { impresiones: 0, likes: 0, respuestas: 0 });

  const refrescar = async () => {
    if (!x || !posts.length) return;
    setEstado("cargando");
    try {
      const r = await api("/api/metricas/x", {
        metodo: "POST",
        cuerpo: { x, ids: posts.map((e) => e.x.id).slice(0, 100) },
      });
      setMetricas(r.metricas || {});
      setEstado("");
    } catch (e) {
      setEstado(e.message);
    }
  };

  const limpiar = () => {
    if (!window.confirm(t("metricas.confirmar_borrar"))) return;
    borrarEnvios();
    setEnvios([]);
    setMetricas({});
  };

  if (!envios.length) {
    return (
      <>
        <h1 className="page-title">{t("nav.metricas")}</h1>
        <p className="page-sub">{t("metricas.subtitulo")}</p>
        <Vacio texto={t("metricas.vacio")} />
      </>
    );
  }

  return (
    <>
      <h1 className="page-title">{t("nav.metricas")}</h1>
      <p className="page-sub">{t("metricas.subtitulo")}</p>

      <div style={{ display: "grid", gap: 10, marginBottom: 14,
                    gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}>
        <Tarjeta titulo={t("metricas.correos")}
                 valor={fmtNum(totales.correos_ok, getIdioma())}
                 pie={t("metricas.de_total", { n: fmtNum(totales.correos, getIdioma()) })}
                 color="var(--green-deep)" />
        <Tarjeta titulo="LinkedIn"
                 valor={fmtNum(totales.li_ok, getIdioma())}
                 pie={t("metricas.de_total", { n: fmtNum(totales.li, getIdioma()) })} />
        <Tarjeta titulo={t("metricas.posts_x")} valor={fmtNum(totales.posts, getIdioma())}
                 pie={t("metricas.publicados")} />
        <Tarjeta titulo={t("metricas.impresiones")}
                 valor={fmtNum(sumaX.impresiones, getIdioma())}
                 pie={t("metricas.en_x")} />
        <Tarjeta titulo={t("metricas.interacciones")}
                 valor={fmtNum(sumaX.likes + sumaX.respuestas, getIdioma())}
                 pie={t("metricas.likes_respuestas")} />
      </div>

      <div className="toolbar" style={{ flexWrap: "wrap" }}>
        <button className="btn" disabled={!x || !posts.length || estado === "cargando"}
                title={x ? "" : t("metricas.x_falta")} onClick={refrescar}>
          {estado === "cargando" ? t("metricas.cargando") : t("metricas.refrescar")}
        </button>
        <button className="btn ghost" onClick={limpiar}>{t("metricas.borrar")}</button>
        <span className="nota" style={{ marginTop: 0 }}>
          {t("metricas.envios", { n: envios.length })}
        </span>
      </div>
      {!x && posts.length ? <Aviso>{t("metricas.x_falta")}</Aviso> : null}
      {estado && estado !== "cargando" ? <p className="error-note">{estado}</p> : null}

      {/* Por publicación: cada post de X con sus números en vivo. */}
      {posts.length ? (
        <>
          <h3 style={{ margin: "18px 0 8px" }}>{t("metricas.por_publicacion")}</h3>
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  <th>{t("metricas.fecha")}</th>
                  <th>{t("metricas.post")}</th>
                  <th className="tnum">{t("metricas.impresiones")}</th>
                  <th className="tnum">{t("metricas.likes")}</th>
                  <th className="tnum">{t("metricas.respuestas")}</th>
                  <th className="tnum">{t("metricas.retweets")}</th>
                </tr>
              </thead>
              <tbody>
                {posts.map((e) => {
                  const m = metricas[e.x.id];
                  const celda = (clave) => (m?.ok
                    ? fmtNum(m[clave], getIdioma())
                    : <span className="apagado">—</span>);
                  return (
                    <tr key={e.x.id}>
                      <td>{fecha(e.fecha)}</td>
                      <td style={{ whiteSpace: "normal", maxWidth: 320 }}>
                        <a href={urlSegura(e.x.url)} target="_blank" rel="noreferrer">
                          {e.x.texto || e.x.url}
                        </a>
                        {m && !m.ok ? (
                          <span className="apagado"> · {m.detalle}</span>
                        ) : null}
                      </td>
                      <td className="tnum">{celda("impresiones")}</td>
                      <td className="tnum">{celda("likes")}</td>
                      <td className="tnum">{celda("respuestas")}</td>
                      <td className="tnum">{celda("retweets")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {/* Por automatización: qué salió por cada canal, tanda por tanda. */}
      <h3 style={{ margin: "18px 0 8px" }}>{t("metricas.por_envio")}</h3>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>{t("metricas.fecha")}</th>
              <th>{t("metricas.producto")}</th>
              <th className="tnum">{t("metricas.correos")}</th>
              <th className="tnum">LinkedIn</th>
              <th>{t("metricas.posts_x")}</th>
              <th>{t("metricas.manual")}</th>
            </tr>
          </thead>
          <tbody>
            {envios.map((e, i) => (
              <tr key={`${e.fecha}-${i}`}>
                <td>{fecha(e.fecha)}</td>
                <td>{e.dominio || "—"}</td>
                <td className="tnum">
                  {e.correos?.total
                    ? `${e.correos.enviados}/${e.correos.total}`
                    : <span className="apagado">—</span>}
                </td>
                <td className="tnum">
                  {e.linkedin?.total
                    ? `${e.linkedin.enviados}/${e.linkedin.total}`
                    : <span className="apagado">—</span>}
                </td>
                <td>
                  {e.x
                    ? (e.x.ok
                        ? <a href={urlSegura(e.x.url)} target="_blank" rel="noreferrer">✔</a>
                        : "✘")
                    : <span className="apagado">—</span>}
                </td>
                <td style={{ whiteSpace: "normal" }}>
                  {Object.entries(e.manuales || {}).length
                    ? Object.entries(e.manuales).map(([c, n]) => `${c} ${n}`).join(" · ")
                    : <span className="apagado">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

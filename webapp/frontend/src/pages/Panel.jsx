import React, { useEffect, useState } from "react";
import { api, ErrorApi, fmtNum, getOwner } from "../api.js";
import { Aviso } from "../componentes/Comunes.jsx";
import { Icono } from "../componentes/Iconos.jsx";
import { t } from "../i18n/index.js";

/**
 * El panel del DUEÑO: cuántos clientes, cuántas descargas y cuánta plata.
 *
 * No es la pestaña «Métricas» —esa mide las campañas del CLIENTE (a qué
 * segmento le fue mejor, a qué hora, cuántos clicks)—. Esto mide el NEGOCIO:
 * ventas, recaudación y descargas del producto.
 *
 * Los números no salen de una base de datos nuestra: las descargas las cuenta
 * GitHub y las ventas MercadoPago. Los dos ya tienen el dato y ninguno se
 * puede desincronizar de la realidad, que es lo que pasa con un contador
 * propio en cuanto un deploy se pierde un evento.
 *
 * La pantalla sólo existe si hay código de dueño guardado: para cualquier
 * otro, el backend contesta 403 y acá ni se ofrece el enlace.
 */
function Tarjeta({ icono, titulo, valor, nota }) {
  return (
    <div className="card" style={{ padding: "16px 18px", minWidth: 168, flex: "1 1 168px" }}>
      <div className="con-ico" style={{ color: "var(--muted)", fontSize: 13, fontWeight: 700 }}>
        <Icono nombre={icono} tam={15} />
        {titulo}
      </div>
      <div className="tnum" style={{ fontSize: 30, fontWeight: 800, margin: "6px 0 2px" }}>
        {valor}
      </div>
      {nota ? <div style={{ color: "var(--faint)", fontSize: 12 }}>{nota}</div> : null}
    </div>
  );
}

export default function Panel() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  const traer = () => {
    setCargando(true);
    setError("");
    api("/api/panel")
      .then(setDatos)
      .catch((e) => setError(e instanceof ErrorApi ? e.message : String(e)))
      .finally(() => setCargando(false));
  };
  useEffect(() => { if (getOwner()) traer(); }, []);

  if (!getOwner()) {
    return (
      <section>
        <h2>{t("panel.titulo")}</h2>
        <Aviso>{t("panel.sin_codigo")}</Aviso>
      </section>
    );
  }

  const c = datos?.cobros;
  const d = datos?.descargas;
  const i = datos?.interaccion;
  const moneda = (n) => `$ ${fmtNum(Math.round(n || 0))}`;
  const pct = (x) => `${(Number(x || 0) * 100).toFixed(1)}%`;

  return (
    <section>
      <h2>{t("panel.titulo")}</h2>
      <p className="nota" style={{ marginTop: 0 }}>{t("panel.subtitulo")}</p>

      <button className="btn ghost con-ico" type="button" onClick={traer} disabled={cargando}>
        {cargando ? t("common.cargando") : t("panel.actualizar")}
      </button>

      {error ? <p className="error-note">{error}</p> : null}

      {datos ? (
        <>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "16px 0" }}>
            <Tarjeta icono="ficha" titulo={t("panel.clientes")}
                     valor={c ? fmtNum(c.clientes) : "—"}
                     nota={c ? t("panel.ventas", { n: c.ventas }) : null} />
            <Tarjeta icono="tendencia" titulo={t("panel.recaudado")}
                     valor={c ? moneda(c.recaudado) : "—"}
                     nota={c ? t("panel.este_mes", { monto: moneda(c.recaudado_mes) }) : null} />
            <Tarjeta icono="descargar" titulo={t("panel.descargas")}
                     valor={d ? fmtNum(d.total) : "—"}
                     nota={d ? `Android ${fmtNum(d.android)} · PC ${fmtNum(d.pc)}` : null} />
          </div>

          {datos.error_cobros ? <Aviso>{datos.error_cobros}</Aviso> : null}
          {datos.error_descargas ? <Aviso>{datos.error_descargas}</Aviso> : null}
          {datos.error_interaccion ? <Aviso>{datos.error_interaccion}</Aviso> : null}
          {c?.hay_mas ? <Aviso>{t("panel.hay_mas")}</Aviso> : null}

          {/* El embudo, de punta a punta: se mandó → se abrió → entró a la web
              → compró. Las descargas y los cobros dicen QUÉ pasó al final;
              esto dice en qué escalón se cae la gente. */}
          <h3 style={{ margin: "22px 0 8px" }}>{t("panel.interaccion")}</h3>
          {datos.traqueo_activo === false ? (
            <Aviso>{t("panel.traqueo_apagado")}</Aviso>
          ) : null}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "8px 0" }}>
            <Tarjeta icono="sobre" titulo={t("panel.enviados")}
                     valor={i ? fmtNum(i.envios) : "—"}
                     nota={i ? t("panel.por_canal", {
                       d: (i.por_canal || [])
                         .map((f) => `${f.clave} ${fmtNum(f.envios)}`).join(" · ") || "—",
                     }) : null} />
            <Tarjeta icono="diana" titulo={t("panel.aperturas")}
                     valor={i ? fmtNum(i.aperturas) : "—"}
                     nota={i ? pct(i.tasa_apertura) : null} />
            <Tarjeta icono="tendencia" titulo={t("panel.clicks")}
                     valor={i ? fmtNum(i.conversiones) : "—"}
                     nota={i ? t("panel.sobre_apertura", {
                       p: pct(i.tasa_click_sobre_apertura) }) : null} />
            <Tarjeta icono="chequeo_circulo" titulo={t("panel.respuestas")}
                     valor={i ? fmtNum(i.respuestas) : "—"}
                     nota={i ? t("panel.sobre_rastreables", {
                       p: pct(i.tasa_respuesta), n: fmtNum(i.rastreables) }) : null} />
            <Tarjeta icono="globo" titulo={t("panel.visitas")}
                     valor={i ? fmtNum(i.visitas) : "—"}
                     nota={i ? t("panel.del_outbound", {
                       p: pct(i.parte_del_trafico) }) : null} />
          </div>

          {i?.por_canal?.length ? (
            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>{t("panel.canal")}</th>
                    <th style={{ textAlign: "right" }}>{t("panel.enviados")}</th>
                    <th style={{ textAlign: "right" }}>{t("panel.aperturas")}</th>
                    <th style={{ textAlign: "right" }}>{t("panel.clicks")}</th>
                    <th style={{ textAlign: "right" }}>{t("panel.respuestas")}</th>
                    <th style={{ textAlign: "right" }}>{t("panel.tasa")}</th>
                  </tr>
                </thead>
                <tbody>
                  {i.por_canal.map((f) => (
                    <tr key={f.valor}>
                      <td>{f.clave}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{fmtNum(f.envios)}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{fmtNum(f.aperturas)}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{fmtNum(f.conversiones)}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{fmtNum(f.respuestas)}</td>
                      <td className="tnum" style={{ textAlign: "right" }}>{pct(f.tasa)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {i?.por_origen?.length ? (
            <>
              <h3 style={{ margin: "18px 0 8px" }}>{t("panel.origen_trafico")}</h3>
              <div className="tablewrap">
                <table>
                  <tbody>
                    {i.por_origen.slice(0, 12).map((f) => (
                      <tr key={f.valor}>
                        <td>{f.clave}</td>
                        <td className="tnum" style={{ textAlign: "right" }}>{fmtNum(f.visitas)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}

          {c?.ultimos?.length ? (
            <>
              <h3 style={{ margin: "18px 0 8px" }}>{t("panel.ultimas_ventas")}</h3>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t("tabla.creada")}</th>
                      <th>{t("tabla.email")}</th>
                      <th style={{ textAlign: "right" }}>{t("panel.monto")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {c.ultimos.map((v) => (
                      <tr key={v.id}>
                        <td className="tnum">{v.fecha}</td>
                        <td>{v.email}</td>
                        <td className="tnum" style={{ textAlign: "right" }}>{moneda(v.monto)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}

          {d?.por_archivo ? (
            <>
              <h3 style={{ margin: "18px 0 8px" }}>{t("panel.por_archivo")}</h3>
              <div className="tablewrap">
                <table>
                  <tbody>
                    {Object.entries(d.por_archivo).map(([arch, n]) => (
                      <tr key={arch}>
                        <td>{arch}</td>
                        <td className="tnum" style={{ textAlign: "right" }}>{fmtNum(n)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

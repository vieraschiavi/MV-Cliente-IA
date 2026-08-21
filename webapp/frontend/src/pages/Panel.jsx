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
  const moneda = (n) => `$ ${fmtNum(Math.round(n || 0))}`;

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
          {c?.hay_mas ? <Aviso>{t("panel.hay_mas")}</Aviso> : null}

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

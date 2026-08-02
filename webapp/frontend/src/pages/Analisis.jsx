import React, { useState } from "react";
import { api, fmtNum, getClaveIA, getEndpointIA, getProveedorIA } from "../api.js";
import { Aviso, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { getIdioma, t } from "../i18n/index.js";

// Campos financieros del formulario: [clave, i18n]. Todo en la misma moneda,
// la que el usuario use en su negocio — acá no se convierte nada.
const CAMPOS = [
  ["precio", "analisis.precio"],
  ["clientes_iniciales", "analisis.clientes_iniciales"],
  ["nuevos_por_mes", "analisis.nuevos_por_mes"],
  ["churn_pct", "analisis.churn"],
  ["gasto_fijo", "analisis.gasto_fijo"],
  ["costo_por_cliente", "analisis.costo_por_cliente"],
  ["gasto_ads", "analisis.gasto_ads"],
  ["cac", "analisis.cac"],
];

function TablaEscenario({ serie }) {
  const idioma = getIdioma();
  return (
    <div className="tablewrap">
      <table>
        <thead>
          <tr>
            <th>{t("analisis.mes")}</th>
            <th>{t("analisis.clientes")}</th>
            <th>{t("analisis.ingresos")}</th>
            <th>{t("analisis.gastos")}</th>
            <th>{t("analisis.neto_mes")}</th>
            <th>{t("analisis.neto_acum")}</th>
          </tr>
        </thead>
        <tbody>
          {serie.filas.map((f) => (
            <tr key={f.mes}>
              <td className="tnum">{f.mes}</td>
              <td className="tnum">{fmtNum(f.clientes, idioma)}</td>
              <td className="tnum">{fmtNum(f.ingresos, idioma)}</td>
              <td className="tnum">{fmtNum(f.gastos, idioma)}</td>
              <td className="tnum" style={{ color: f.neto_mes >= 0 ? "var(--green-deep)" : "var(--red, #e05555)" }}>
                {fmtNum(f.neto_mes, idioma)}
              </td>
              <td className="tnum" style={{ color: f.neto_acumulado >= 0 ? "var(--green-deep)" : "var(--red, #e05555)" }}>
                {fmtNum(f.neto_acumulado, idioma)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="nota">
        {serie.equilibrio_mes
          ? `${t("analisis.equilibrio")}: ${t("analisis.mes").toLowerCase()} ${serie.equilibrio_mes}`
          : t("analisis.sin_equilibrio")}
      </p>
    </div>
  );
}

function Foda({ foda }) {
  const BLOQUES = [
    ["fortalezas", "analisis.fortalezas"],
    ["debilidades", "analisis.debilidades"],
    ["oportunidades", "analisis.oportunidades"],
    ["amenazas", "analisis.amenazas"],
  ];
  return foda.map((f) => (
    <div className="card" key={f.competidor} style={{ marginBottom: 10 }}>
      <h4 style={{ margin: "0 0 8px" }}>{f.competidor}</h4>
      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
        {BLOQUES.map(([clave, etiqueta]) => (
          <div key={clave}>
            <b style={{ fontSize: 13 }}>{t(etiqueta)}</b>
            <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
              {(f[clave] || []).map((x, i) => <li key={i} style={{ fontSize: 13 }}>{x}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  ));
}

export default function Analisis() {
  const { corrida } = useCorrida(getCorridaId());
  const [form, setForm] = useState(Object.fromEntries(CAMPOS.map(([c]) => [c, ""])));
  const [resultado, setResultado] = useState(null);
  const [escenario, setEscenario] = useState("base");
  const [conAds, setConAds] = useState(true);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  const lanzar = async (e) => {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      const r = await api("/api/analisis", { metodo: "POST", cuerpo: {
        empresa: corrida?.empresa || {},
        competidores: corrida?.competidores || [],
        mercado: corrida?.mercado || "todos",
        idioma: getIdioma(),
        ...Object.fromEntries(CAMPOS.map(([c]) => [c, Number(form[c]) || 0])),
        ...(getClaveIA()
          ? { clave_ia: getClaveIA(), proveedor_ia: getProveedorIA(),
              endpoint_ia: getEndpointIA() }
          : {}),
      } });
      setResultado(r);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  if (!corrida) return <Vacio />;

  const q = resultado?.cualitativo;
  const fin = resultado?.financiero;
  const serie = fin?.escenarios?.[escenario]?.[conAds ? "con_ads" : "sin_ads"];

  return (
    <>
      <h1 className="page-title">{t("analisis.titulo")}</h1>
      <p className="page-sub">{t("analisis.subtitulo")}</p>

      <form className="card" style={{ maxWidth: 760, marginBottom: 14 }} onSubmit={lanzar}>
        <h3>{t("analisis.datos")} · {corrida.empresa?.nombre}</h3>
        <p className="nota" style={{ marginTop: 0 }}>{t("analisis.moneda")}</p>
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          {CAMPOS.map(([clave, etiqueta]) => (
            <div className="campo" key={clave}>
              <label htmlFor={`an-${clave}`}>{t(etiqueta)}</label>
              <input id={`an-${clave}`} type="number" min="0" step="any"
                     value={form[clave]} inputMode="decimal"
                     onChange={(e2) => setForm({ ...form, [clave]: e2.target.value })} />
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12 }}>
          <button className="btn" type="submit" disabled={cargando || !Number(form.precio)}>
            {cargando ? t("analisis.analizando") : t("analisis.analizar")}
          </button>
        </div>
        {error ? <p className="error-note">{error}</p> : null}
      </form>

      {resultado?.avisos?.length ? (
        <Aviso>
          {resultado.avisos.map((a, i) => (
            <div key={i}>{a === "analisis_sin_clave" ? t("analisis.sin_clave") : a}</div>
          ))}
        </Aviso>
      ) : null}

      {q ? (
        <>
          <div className="card" style={{ marginBottom: 14 }}>
            <h3>{t("analisis.exito")}</h3>
            <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
              <span style={{ fontSize: 42, fontWeight: 800, color: "var(--green-deep)" }}>
                {q.probabilidad_exito}%
              </span>
              <p style={{ margin: 0, maxWidth: 640 }}>{q.veredicto}</p>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 14 }}>
            <h3>{t("analisis.mercado")}</h3>
            <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
              {["local", "latam", "mundo"].map((n) => (
                <div key={n}>
                  <span className={`pill ${n}`}>{t(`ola.${n}`)}</span>
                  <p style={{ fontSize: 13.5, marginTop: 6 }}>{q.mercado_potencial[n]}</p>
                </div>
              ))}
            </div>
          </div>

          {q.foda?.length ? (
            <>
              <h3 style={{ margin: "0 0 8px" }}>{t("analisis.foda")}</h3>
              <Foda foda={q.foda} />
            </>
          ) : null}

          {q.riesgos?.length ? (
            <div className="card" style={{ marginBottom: 14 }}>
              <h3>{t("analisis.riesgos")}</h3>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {q.riesgos.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}

      {fin ? (
        <div className="card">
          <h3>{t("analisis.rentabilidad")}</h3>
          <div className="toolbar" style={{ marginBottom: 8 }}>
            <select value={escenario} onChange={(e) => setEscenario(e.target.value)}>
              <option value="pesimista">{t("analisis.pesimista")}</option>
              <option value="base">{t("analisis.base")}</option>
              <option value="optimista">{t("analisis.optimista")}</option>
            </select>
            <select value={conAds ? "1" : "0"} onChange={(e) => setConAds(e.target.value === "1")}>
              <option value="1">{t("analisis.con_ads")}</option>
              <option value="0">{t("analisis.sin_ads")}</option>
            </select>
          </div>
          {serie ? <TablaEscenario serie={serie} /> : null}
          <p className="nota">{t("analisis.supuestos")}</p>
        </div>
      ) : null}
    </>
  );
}

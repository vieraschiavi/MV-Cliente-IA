import React, { useEffect, useMemo, useRef, useState } from "react";
import { api, fmtNum, getClaveIA, getEndpointIA, getProveedorIA } from "../api.js";
import { Aviso, etiquetasOla, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { getIdioma, t } from "../i18n/index.js";

// Campos financieros del formulario: [clave, i18n, ejemplo]. Todo en la
// misma moneda, la que el usuario use en su negocio — acá no se convierte
// nada. El ejemplo del placeholder muestra un caso típico de SaaS chico.
const CAMPOS = [
  ["precio", "analisis.precio", "99"],
  ["clientes_iniciales", "analisis.clientes_iniciales", "0"],
  ["nuevos_por_mes", "analisis.nuevos_por_mes", "3"],
  ["churn_pct", "analisis.churn", "5"],
  ["gasto_fijo", "analisis.gasto_fijo", "500"],
  ["costo_por_cliente", "analisis.costo_por_cliente", "10"],
  ["gasto_ads", "analisis.gasto_ads", "300"],
  ["cac", "analisis.cac", "150"],
];

// Columnas de la proyección: [clave del dato, clave i18n, ¿lleva color?].
// data-col en cada celda es lo que le pone el título a la vista de tarjetas
// del celular — sin él quedaban números sueltos sin etiqueta.
const COLS = [
  ["mes", "analisis.mes", false],
  ["clientes", "analisis.clientes", false],
  ["ingresos", "analisis.ventas", false],
  ["gasto_fijo", "analisis.col_fijo", false],
  ["gasto_variable", "analisis.col_variable", false],
  ["gasto_ads", "analisis.col_ads", false],
  ["gastos", "analisis.gastos", false],
  ["neto_mes", "analisis.neto_mes", true],
  ["neto_acumulado", "analisis.neto_acum", true],
];

function TablaEscenario({ serie }) {
  const idioma = getIdioma();
  return (
    <div className="tablewrap">
      <table>
        <thead>
          <tr>{COLS.map(([, clave]) => <th key={clave}>{t(clave)}</th>)}</tr>
        </thead>
        <tbody>
          {serie.filas.map((f) => (
            <tr key={f.mes}>
              {COLS.map(([campo, clave, coloreada]) => (
                <td key={campo} className="tnum" data-col={t(clave)}
                    style={coloreada
                      ? { color: f[campo] >= 0 ? "var(--green-deep)" : "var(--red, #e05555)" }
                      : undefined}>
                  {campo === "mes" ? f.mes : fmtNum(f[campo], idioma)}
                </td>
              ))}
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

/** Precio leído del texto real del sitio ("desde USD 99", "$ 4.990/mes"…).
 *  Es una precarga editable, no una verdad: si no aparece, queda manual. */
function precioDelSitio(empresa) {
  const texto = `${empresa?.resumen_sitio || ""} ${empresa?.propuesta || ""}`;
  const m = texto.match(
    /(?:desde|from|a partir de)?\s*(?:US?\$|USD|U\$S|R\$|\$U|\$|€)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)/i);
  if (!m) return 0;
  // "4.990" es un separador de miles; "99.90" son centavos.
  const crudo = m[1].replace(/[.,](?=\d{3}(?:\D|$))/g, "").replace(",", ".");
  const n = Number(crudo);
  return Number.isFinite(n) && n >= 1 ? Math.round(n) : 0;
}

export default function Analisis() {
  const { corrida } = useCorrida(getCorridaId());
  const [form, setForm] = useState(Object.fromEntries(CAMPOS.map(([c]) => [c, ""])));

  // Precarga automática con fallback manual: el precio sale de la web del
  // producto y los clientes nuevos se estiman de los prospectos de la
  // corrida con una conversión declarada del 3%. Todo queda editable y la
  // nota de abajo dice de dónde salió cada número.
  const sugerencias = useMemo(() => ({
    precio: precioDelSitio(corrida?.empresa),
    prospectos: (corrida?.prospectos || []).length,
    nuevos: (corrida?.prospectos || []).length
      ? Math.max(1, Math.round((corrida?.prospectos || []).length * 0.03)) : 0,
  }), [corrida]);
  const precargado = useRef(false);
  useEffect(() => {
    if (precargado.current || !corrida) return;
    precargado.current = true;
    setForm((f) => ({
      ...f,
      precio: f.precio || (sugerencias.precio ? String(sugerencias.precio) : ""),
      nuevos_por_mes: f.nuevos_por_mes
        || (sugerencias.nuevos ? String(sugerencias.nuevos) : ""),
    }));
  }, [corrida, sugerencias]);
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

  // ¿Hay alguna vía de entrada de clientes cargada? Sin ninguna, los tres
  // escenarios dan cero seguro y hay que decirlo, no mostrarlo.
  const sinEntrada = !Number(form.clientes_iniciales) && !Number(form.nuevos_por_mes)
    && !(Number(form.gasto_ads) > 0 && Number(form.cac) > 0);

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
        {sugerencias.precio || sugerencias.nuevos ? (
          <p className="nota" style={{ marginTop: 0 }}>
            {sugerencias.precio ? `${t("analisis.prefill_precio")} ` : ""}
            {sugerencias.nuevos
              ? t("analisis.prefill_clientes",
                  { n: sugerencias.prospectos, est: sugerencias.nuevos })
              : ""}
          </p>
        ) : null}
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          {CAMPOS.map(([clave, etiqueta, ejemplo]) => (
            <div className="campo" key={clave}>
              <label htmlFor={`an-${clave}`}>{t(etiqueta)}</label>
              <input id={`an-${clave}`} type="number" min="0" step="any"
                     value={form[clave]} inputMode="decimal"
                     placeholder={`${t("analisis.ej")} ${ejemplo}`}
                     onChange={(e2) => setForm({ ...form, [clave]: e2.target.value })} />
            </div>
          ))}
        </div>
        {/* Sin clientes actuales, sin altas por mes y sin ads con CAC, la
            proyección da cero por definición — se avisa ANTES de mostrar
            una tabla llena de ceros que parece un bug. */}
        {sinEntrada ? <p className="nota" style={{ marginBottom: 0 }}>{t("analisis.sin_movimiento")}</p> : null}
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
              {["local", "regional", "mundo"].map((n) => (
                <div key={n}>
                  <span className={`pill ${n}`}>{etiquetasOla(corrida)[n]}</span>
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

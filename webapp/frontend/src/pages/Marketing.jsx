import React, { useState } from "react";
import { api, fmtNum, getEnvios, urlSegura } from "../api.js";
import { Aviso, Kpis, Vacio } from "../componentes/Comunes.jsx";
import { Icono } from "../componentes/Iconos.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { getIdioma, mensajeDeError, t } from "../i18n/index.js";
import { leerAnalisis } from "./Analisis.jsx";

/**
 * Marketing digital del cliente: su sitio y sus redes medidos, puestos al
 * lado de la competencia de la corrida, y los KPI del embudo comercial.
 *
 * La auditoría la hace el servidor (cliente_ia/marketing.py) y NO usa IA:
 * cada número sale de leer el sitio o de una cifra pública con su fecha. El
 * resultado se guarda en este dispositivo por corrida, para no volver a
 * pedírselo a los sitios cada vez que se abre la pestaña.
 */
const REDES = ["linkedin", "instagram", "facebook", "tiktok"];
const ICONO_RED = { linkedin: "maletin", instagram: "camara", tiktok: "musica", facebook: "pulgar" };
const AREAS = ["seo", "medicion", "conversion", "redes", "tecnica"];
const MEDICION = ["ga4", "gtm", "google_ads", "meta_pixel", "linkedin_insight",
                  "tiktok_pixel", "hotjar", "clarity", "hubspot"];
const CANALES = ["formulario", "whatsapp", "email", "telefono", "chat"];

const claveCache = (id) => `mvcliente_marketing_${id}`;
function leerCache(id) {
  try { return JSON.parse(localStorage.getItem(claveCache(id))) || null; } catch { return null; }
}
function guardarCache(id, datos) {
  try { localStorage.setItem(claveCache(id), JSON.stringify(datos)); } catch { /* sin cupo */ }
}

const num = (n) => fmtNum(n, getIdioma());
const pct = (x) => `${Math.round((x || 0) * 100)}%`;
const colorPuntaje = (p) => (p == null ? "var(--muted)" : p >= 70 ? "var(--green-deep)"
  : p >= 45 ? "var(--amber)" : "var(--red)");

// `color` fijo para volúmenes (embudo, cuota): el semáforo es para puntajes;
// pintar de rojo «60 empresas» se leía como algo malo.
function Barra({ valor, color }) {
  return (
    <div className="mk-barra" aria-hidden="true">
      <i style={{ width: `${Math.min(100, valor ?? 0)}%`, background: color || colorPuntaje(valor) }} />
    </div>
  );
}

function Check({ ok, children }) {
  return (
    <li className={ok ? "ok" : "no"}>
      <Icono nombre={ok ? "chequeo_circulo" : "equis_circulo"} tam={15} />
      <span>{children}</span>
    </li>
  );
}

function Subpuntajes({ a }) {
  return (
    <div className="card">
      <h3>{t("marketing.puntaje_por_area")}</h3>
      {AREAS.map((k) => {
        const v = a.puntajes.sub[k];
        return (
          <div className="mk-area" key={k}>
            <span>{t(`marketing.area_${k}`)} <small>· {t("marketing.pesa", { p: a.pesos[k] })}</small></span>
            <Barra valor={v} />
            <b className="tnum" style={{ color: colorPuntaje(v) }}>{v == null ? "—" : v}</b>
          </div>
        );
      })}
      <p className="nota">{t("marketing.puntaje_ayuda")}</p>
    </div>
  );
}

function Recomendaciones({ lista }) {
  if (!lista.length) return <div className="card"><h3>{t("marketing.recomendaciones")}</h3>
    <p className="nota" style={{ marginTop: 0 }}>{t("marketing.sin_recomendaciones")}</p></div>;
  return (
    <div className="card">
      <h3>{t("marketing.recomendaciones")}</h3>
      <ol className="mk-reco">
        {lista.map((r) => (
          <li key={r.codigo}>
            <span className={`pill mk-${r.prioridad}`}>{t(`marketing.prioridad_${r.prioridad}`)}</span>
            <span>{t(`marketing.reco.${r.codigo}`, r.datos || {})}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Detalle({ a }) {
  const s = a.seo, c = a.conversion, tec = a.tecnica;
  return (
    <div className="mk-grid">
      <div className="card">
        <h3>{t("marketing.area_seo")}</h3>
        <ul className="mk-checks">
          <Check ok={s.largo_titulo >= 30 && s.largo_titulo <= 65}>{t("marketing.seo_titulo", { n: s.largo_titulo })}</Check>
          <Check ok={s.largo_descripcion >= 70 && s.largo_descripcion <= 160}>{t("marketing.seo_descripcion", { n: s.largo_descripcion })}</Check>
          <Check ok={s.h1 === 1}>{t("marketing.seo_h1", { n: s.h1 })}</Check>
          <Check ok={s.canonical}>{t("marketing.seo_canonical")}</Check>
          <Check ok={s.viewport}>{t("marketing.seo_viewport")}</Check>
          <Check ok={s.open_graph}>{t("marketing.seo_og")}</Check>
          <Check ok={s.schema.length > 0}>{t("marketing.seo_schema")}{s.schema.length ? `: ${s.schema.join(", ")}` : ""}</Check>
          <Check ok={Boolean(s.lang)}>{t("marketing.seo_idiomas")}: {[...new Set([s.lang, ...s.idiomas]
            .filter((x) => x && x !== "x-default").map((x) => x.slice(0, 2).toLowerCase()))].join(", ") || "—"}</Check>
          <Check ok={!s.imagenes || s.imagenes_sin_alt / s.imagenes <= 0.2}>{t("marketing.seo_alt", { n: s.imagenes_sin_alt, total: s.imagenes })}</Check>
          <Check ok={s.palabras >= 300}>{t("marketing.seo_palabras", { n: num(s.palabras) })}</Check>
        </ul>
      </div>
      <div className="card">
        <h3>{t("marketing.area_medicion")}</h3>
        <ul className="mk-checks">
          {MEDICION.map((m) => <Check key={m} ok={a.medicion[m]}>{t(`marketing.tag_${m}`)}</Check>)}
        </ul>
        <p className="nota">{t("marketing.medicion_ayuda")}</p>
      </div>
      <div className="card">
        <h3>{t("marketing.area_conversion")}</h3>
        <ul className="mk-checks">
          {CANALES.map((k) => <Check key={k} ok={c[k]}>{t(`marketing.canal_${k}`)}</Check>)}
          <Check ok={c.cta > 0}>{t("marketing.canal_cta", { n: c.cta })}</Check>
        </ul>
      </div>
      <div className="card">
        <h3>{t("marketing.area_tecnica")}</h3>
        <ul className="mk-checks">
          <Check ok={tec.https}>HTTPS</Check>
          <Check ok={tec.ms <= 1500}>{t("marketing.tec_ms", { ms: num(tec.ms) })}</Check>
          <Check ok={tec.kb <= 1500}>{t("marketing.tec_kb", { kb: num(tec.kb) })}</Check>
          <Check ok={tec.robots}>robots.txt</Check>
          <Check ok={tec.sitemap}>sitemap.xml</Check>
        </ul>
        <p className="nota">{t("marketing.tec_ayuda")}</p>
      </div>
    </div>
  );
}

function Redes({ a }) {
  const perfiles = REDES.filter((r) => a.redes[r]);
  return (
    <div className="card">
      <h3>{t("marketing.area_redes")}</h3>
      {perfiles.length ? (
        <div className="mk-redes">
          {perfiles.map((r) => {
            const m = a.metricas[r];
            const ok = m && m.estado === "ok";
            return (
              <a key={r} href={urlSegura(a.redes[r])} target="_blank" rel="noreferrer"
                 className="mk-red" title={ok ? t("competencia.metrica_fuente", { fecha: m.fecha }) : t("competencia.metrica_nd")}>
                <Icono nombre={ICONO_RED[r]} tam={18} />
                <span className="red">{r}</span>
                <b className="tnum">{ok ? num(m.seguidores) : "—"}</b>
                <small>{ok ? t("competencia.seguidores") : t("marketing.no_disponible")}</small>
              </a>
            );
          })}
        </div>
      ) : <p className="nota" style={{ marginTop: 0 }}>{t("marketing.reco.sin_redes")}</p>}
    </div>
  );
}

function Competencia({ a }) {
  const cuota = Object.entries(a.cuota_de_voz || {});
  const filas = [{ dominio: a.dominio, nombre: t("marketing.vos"), puntaje: a.puntajes.total,
                   seo: a.puntajes.sub.seo, medicion: a.medicion, conversion: a.conversion, propio: true },
                 ...a.benchmark].sort((x, y) => (y.puntaje ?? -1) - (x.puntaje ?? -1));
  return (
    <div className="card">
      <h3>{t("marketing.vs_competencia")}</h3>
      {a.benchmark.length ? (
        <div className="tablewrap">
          <table>
            <thead><tr>
              <th>{t("tabla.empresa")}</th><th>{t("marketing.col_puntaje")}</th><th>SEO</th>
              <th>{t("marketing.area_medicion")}</th><th>{t("marketing.area_conversion")}</th>
            </tr></thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.dominio} className={f.propio ? "mk-propio" : ""}>
                  <td data-col={t("tabla.empresa")}>{f.nombre}{f.propio ? null : <small className="nota"> · {f.dominio}</small>}</td>
                  {f.error ? <td colSpan={4} data-col={t("marketing.col_puntaje")}>{t("marketing.no_se_pudo_leer")}</td> : <>
                    <td className="tnum" data-col={t("marketing.col_puntaje")} style={{ color: colorPuntaje(f.puntaje), fontWeight: 800 }}>{f.puntaje}</td>
                    <td className="tnum" data-col="SEO">{f.seo}</td>
                    <td className="tnum" data-col={t("marketing.area_medicion")}>{Object.values(f.medicion).filter(Boolean).length}/{MEDICION.length}</td>
                    <td className="tnum" data-col={t("marketing.area_conversion")}>{CANALES.filter((k) => f.conversion[k]).length}/{CANALES.length}</td>
                  </>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="nota" style={{ marginTop: 0 }}>{t("marketing.sin_competencia")}</p>}
      {cuota.length ? (
        <>
          <h4 className="sub" style={{ marginTop: 16 }}>{t("marketing.cuota_de_voz")}</h4>
          {cuota.map(([red, c]) => (
            <div className="mk-area" key={red}>
              <span className="con-ico"><Icono nombre={ICONO_RED[red]} tam={14} /> {red}</span>
              {c.cuota == null ? (
                // Sin cifra propia no hay cuota que dibujar: se dice cuánto
                // junta la competencia, que es el dato útil igual.
                <span className="nota" style={{ margin: 0 }}>
                  {t("marketing.cuota_sin_propia", { n: num(c.competencia), k: c.competidores_medidos })}
                </span>
              ) : <Barra valor={c.cuota * 100} color="var(--green-deep)" />}
              <b className="tnum">{c.cuota == null ? "—" : pct(c.cuota)}</b>
            </div>
          ))}
          <p className="nota">{t("marketing.cuota_ayuda")}</p>
        </>
      ) : null}
    </div>
  );
}

/** KPI del embudo comercial con los números que ya tiene la app: la corrida
 *  (empresas, decisores, correos), los envíos de este dispositivo (Métricas)
 *  y los supuestos que el usuario cargó en Análisis. Sin ellos, no hay KPI. */
function Embudo({ corrida }) {
  // Mismo registro que la pestaña Métricas (Correos.jsx:agregarEnvio):
  // correos y mensajes de LinkedIn enviados de verdad desde esta corrida.
  const enviados = getEnvios()
    .filter((e) => e.corrida_id === corrida.id)
    .reduce((n, e) => n + (Number(e.correos?.enviados) || 0) + (Number(e.linkedin?.enviados) || 0), 0);
  const pasos = [
    [t("marketing.emb_empresas"), (corrida.prospectos || []).length],
    [t("marketing.emb_decisores"), (corrida.decisores || []).length],
    [t("marketing.emb_correos"), (corrida.emails || []).length],
    [t("marketing.emb_enviados"), enviados],
  ];
  const tope = Math.max(1, ...pasos.map(([, n]) => n));
  const f = leerAnalisis();
  const precio = Number(f.precio) || 0, costo = Number(f.costo_por_cliente) || 0;
  const churn = (Number(f.churn_pct) || 0) / 100, cac = Number(f.cac) || 0;
  const margen = precio - costo;
  const ltv = margen > 0 && churn > 0 ? margen / churn : null;
  return (
    <div className="card">
      <h3>{t("marketing.embudo")}</h3>
      {pasos.map(([etq, n], i) => (
        <div className="mk-area" key={etq}>
          <span>{etq}</span>
          <Barra valor={(n / tope) * 100} color="var(--green-deep)" />
          <b className="tnum">{num(n)}{i && pasos[i - 1][1] ? <small> · {i === 1
            // Decisores por empresa, no un porcentaje: «300 %» no se lee
            // como conversión.
            ? t("marketing.por_empresa", { n: (n / pasos[0][1]).toFixed(1) })
            : pct(n / pasos[i - 1][1])}</small> : null}</b>
        </div>
      ))}
      <h4 className="sub" style={{ marginTop: 16 }}>{t("marketing.unitarios")}</h4>
      {precio ? (
        <Kpis items={[
          { label: "LTV", valor: ltv == null ? "—" : num(Math.round(ltv)), delta: t("marketing.ltv_ayuda") },
          { label: "CAC", valor: cac ? num(cac) : "—", delta: t("marketing.cac_ayuda") },
          { label: "LTV : CAC", valor: ltv && cac ? `${(ltv / cac).toFixed(1)}×` : "—", delta: t("marketing.ratio_ayuda") },
          { label: t("marketing.payback"), valor: cac && margen > 0 ? `${(cac / margen).toFixed(1)} ${t("marketing.meses")}` : "—", delta: t("marketing.payback_ayuda") },
        ]} />
      ) : <p className="nota" style={{ marginTop: 0 }}>{t("marketing.sin_analisis")}</p>}
    </div>
  );
}

export default function Marketing() {
  const { corrida } = useCorrida(getCorridaId());
  const id = corrida?.id;
  const [auditoria, setAuditoria] = useState(() => (getCorridaId() ? leerCache(getCorridaId()) : null));
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  if (!corrida) return <Vacio />;
  const a = auditoria && auditoria.dominio ? auditoria : null;

  const auditar = async () => {
    setCargando(true);
    setError("");
    try {
      const r = await api("/api/marketing", { metodo: "POST", cuerpo: {
        dominio: corrida.dominio,
        competidores: (corrida.competidores || []).slice(0, 6).map((c) => ({
          dominio: c.dominio, nombre: c.nombre || "", metricas: c.metricas || {} })),
      } });
      setAuditoria(r);
      guardarCache(id, r);
    } catch (e) {
      setError(e.status === 429 ? t("marketing.limite") : mensajeDeError(e.message));
    } finally {
      setCargando(false);
    }
  };

  const seguidores = a ? REDES.reduce((n, r) => n + (a.metricas[r]?.estado === "ok" ? a.metricas[r].seguidores : 0), 0) : 0;
  return (
    <>
      <h1 className="page-title">{t("nav.marketing")}</h1>
      <p className="page-sub">{t("marketing.sub")}</p>
      <div className="toolbar">
        <button className="btn primary con-ico" onClick={auditar} disabled={cargando}>
          <Icono nombre="megafono" tam={16} />
          {cargando ? t("marketing.auditando") : a ? t("marketing.reauditar") : t("marketing.auditar")}
        </button>
        <span className="nota" style={{ marginTop: 0 }}>
          {a ? t("marketing.medido_el", { dominio: a.dominio, fecha: a.fecha }) : corrida.dominio}
        </span>
      </div>
      {error ? <p className="error-note">{error}</p> : null}
      {auditoria?.error ? <Aviso>{t("marketing.no_se_pudo_leer_sitio", { dominio: auditoria.dominio })}</Aviso> : null}
      {a && !a.error ? (
        <>
          <Kpis items={[
            { label: t("marketing.kpi_presencia"), valor: `${a.puntajes.total}/100`, delta: t("marketing.kpi_presencia_ayuda"),
              color: colorPuntaje(a.puntajes.total) },
            { label: t("marketing.kpi_seguidores"), valor: seguidores ? num(seguidores) : "—",
              delta: t("marketing.kpi_seguidores_ayuda"), color: seguidores ? undefined : "var(--muted)" },
            { label: t("marketing.kpi_medicion"), valor: `${Object.values(a.medicion).filter(Boolean).length}/${MEDICION.length}`,
              delta: t("marketing.kpi_medicion_ayuda"), color: colorPuntaje(a.puntajes.sub.medicion) },
            { label: t("marketing.kpi_conversion"), valor: `${CANALES.filter((k) => a.conversion[k]).length}/${CANALES.length}`,
              delta: t("marketing.kpi_cta", { n: a.conversion.cta }), color: colorPuntaje(a.puntajes.sub.conversion) },
            { label: t("marketing.kpi_velocidad"), valor: `${num(a.tecnica.ms)} ms`, delta: `${num(a.tecnica.kb)} KB`,
              color: colorPuntaje(a.tecnica.ms <= 1500 ? 100 : a.tecnica.ms <= 3000 ? 50 : 0) },
          ]} />
          <div className="mk-grid" style={{ marginTop: 14 }}>
            <Subpuntajes a={a} />
            <Recomendaciones lista={a.recomendaciones} />
          </div>
          <div style={{ marginTop: 14 }}><Redes a={a} /></div>
          <div style={{ marginTop: 14 }}><Competencia a={a} /></div>
          <div style={{ marginTop: 14 }}><Detalle a={a} /></div>
        </>
      ) : !auditoria ? <Aviso>{t("marketing.explicacion")}</Aviso> : null}
      <div style={{ marginTop: 14 }}><Embudo corrida={corrida} /></div>
    </>
  );
}

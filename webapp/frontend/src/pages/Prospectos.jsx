import React, { useState } from "react";
import { fmtScore, urlSegura } from "../api.js";
import { etiquetasOla, Ola, Tabla, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { t } from "../i18n/index.js";

export default function Prospectos() {
  const { corrida } = useCorrida(getCorridaId());
  const [nivel, setNivel] = useState("");

  const todos = corrida?.prospectos || [];
  const etiquetas = etiquetasOla(corrida);
  const filas = nivel ? todos.filter((p) => p.nivel === nivel) : todos;

  const columnas = [
    { id: "score", titulo: t("tabla.score"),
      render: (p) => <b className="tnum" style={{ color: "var(--green-deep)" }}>{fmtScore(p.score)}</b> },
    { id: "ola", titulo: t("tabla.ola"), render: (p) => <Ola nivel={p.nivel} etiquetas={etiquetas} /> },
    { id: "empresa", titulo: t("tabla.empresa"), render: (p) => p.nombre },
    { id: "sector", titulo: t("tabla.sector"), render: (p) => p.sector },
    { id: "pais", titulo: t("tabla.pais"), render: (p) => `${p.pais} · ${p.ciudad}` },
    { id: "empleados", titulo: t("tabla.empleados"),
      render: (p) => <span className="tnum">{p.empleados || "—"}</span> },
    { id: "dominio", titulo: t("tabla.dominio"), render: (p) => p.dominio },
    { id: "contacto", titulo: t("tabla.contacto"),
      // Contactos PÚBLICOS leídos del sitio de la empresa real; los
      // sintéticos no tienen (sus dominios no existen).
      render: (p) => {
        const c = p.contactos || {};
        const enlaces = [
          c.email ? <a key="m" href={`mailto:${c.email}`} title={c.email}>✉ {c.email}</a> : null,
          c.telefono ? <a key="t" href={`tel:${c.telefono}`}>☎ {c.telefono}</a> : null,
          c.linkedin ? <a key="l" href={urlSegura(c.linkedin)} target="_blank" rel="noreferrer">LinkedIn</a> : null,
          c.instagram ? <a key="i" href={urlSegura(c.instagram)} target="_blank" rel="noreferrer">Instagram</a> : null,
        ].filter(Boolean);
        return enlaces.length
          ? <span style={{ display: "inline-flex", gap: 10, flexWrap: "wrap", whiteSpace: "normal" }}>{enlaces}</span>
          : "—";
      } },
    { id: "senales", titulo: t("tabla.senales"),
      // "Por qué ahora" puede traer varias señales: sin tope, el texto se
      // apila y estira la fila a 300px. Se limita a 2 líneas con el texto
      // completo en el title, y un ancho que evita que la columna se
      // aplaste contra el borde derecho de la tabla.
      render: (p) => {
        const txt = (p.senales || []).join(" · ");
        return <span className="celda-2l" title={txt}>{txt}</span>;
      } },
  ];

  if (!corrida) return <Vacio />;

  return (
    <>
      <h1 className="page-title">{t("nav.prospectos")}</h1>
      <p className="page-sub">{t("ola.explicacion")}</p>
      <div className="toolbar">
        <select value={nivel} onChange={(e) => setNivel(e.target.value)}>
          <option value="">{t("correos.todos")}</option>
          <option value="local">{etiquetas.local}</option>
          <option value="regional">{etiquetas.regional}</option>
          <option value="mundo">{etiquetas.mundo}</option>
        </select>
        <span className="nota" style={{ marginTop: 0 }}>
          {filas.length} {t("common.de")} {todos.length}
        </span>
      </div>
      <Tabla columnas={columnas} filas={filas} clave={(p) => p.id} />
    </>
  );
}

import React, { useState } from "react";
import { fmtScore } from "../api.js";
import { etiquetasOla, Idioma, Ola, Tabla, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { t } from "../i18n/index.js";

export default function Decisores() {
  const { corrida } = useCorrida(getCorridaId());
  const [nivel, setNivel] = useState("");

  const etiquetas = etiquetasOla(corrida);
  const porProspecto = Object.fromEntries((corrida?.prospectos || []).map((p) => [p.id, p]));
  const todos = (corrida?.decisores || []).map((d) => ({ ...d, prospecto: porProspecto[d.prospecto_id] }));
  const filas = nivel ? todos.filter((d) => d.prospecto?.nivel === nivel) : todos;

  const columnas = [
    { id: "score", titulo: t("tabla.score"),
      render: (d) => <b className="tnum" style={{ color: "var(--green-deep)" }}>{fmtScore(d.score)}</b> },
    { id: "ola", titulo: t("tabla.ola"),
      render: (d) => (d.prospecto
        ? <Ola nivel={d.prospecto.nivel} etiquetas={etiquetas} /> : "—") },
    { id: "decisor", titulo: t("tabla.decisor"),
      // Empresa real → no se inventa la persona: se muestra la búsqueda de
      // LinkedIn armada con el cargo. Sintético → el nombre con su marca.
      render: (d) => (d.nombre
        ? <>{d.nombre} {d.sintetico ? <span className="pill mundo">{t("decisores.sintetico")}</span> : null}</>
        : (d.linkedin
            ? <a href={d.linkedin} target="_blank" rel="noreferrer">
                {/* Con la página de la empresa conocida, el enlace lleva a
                    sus empleados ACTUALES filtrados por el cargo. */}
                {d.linkedin.includes("/company/")
                  ? t("decisores.gente_linkedin") : t("decisores.buscar_linkedin")}
              </a>
            : "—")) },
    { id: "cargo", titulo: t("tabla.cargo"), render: (d) => d.cargo },
    { id: "empresa", titulo: t("tabla.empresa"), render: (d) => d.empresa },
    { id: "pais", titulo: t("tabla.pais"), render: (d) => d.pais },
    { id: "email", titulo: t("tabla.email"),
      // Sin persona identificada se muestra la casilla comercial que la
      // empresa publica en su sitio; sin casilla, el resto de sus canales
      // públicos (teléfono, LinkedIn, Instagram) — recién sin nada de nada
      // se explica por qué está vacío.
      render: (d) => {
        if (d.email) return d.email;
        const c = d.prospecto?.contactos || {};
        if (c.email) {
          return <>
            <a href={`mailto:${c.email}`}>{c.email}</a>{" "}
            <span className="pill mundo">{t("decisores.correo_empresa")}</span>
          </>;
        }
        const canales = [
          c.telefono ? <a key="t" href={`tel:${c.telefono}`}>☎ {c.telefono}</a> : null,
          c.linkedin ? <a key="l" href={c.linkedin} target="_blank" rel="noreferrer">LinkedIn</a> : null,
          c.instagram ? <a key="i" href={c.instagram} target="_blank" rel="noreferrer">Instagram</a> : null,
        ].filter(Boolean);
        if (canales.length) {
          return <span style={{ display: "inline-flex", gap: 10, flexWrap: "wrap" }}>
            {canales} <span className="pill mundo">{t("decisores.canales_empresa")}</span>
          </span>;
        }
        return <span className="nota" style={{ margin: 0 }}>{t("decisores.sin_correo")}</span>;
      } },
    { id: "idioma", titulo: t("tabla.idioma"), render: (d) => <Idioma codigo={d.idioma} /> },
  ];

  if (!corrida) return <Vacio />;

  return (
    <>
      <h1 className="page-title">{t("nav.decisores")}</h1>
      <p className="page-sub">{t("fase.decisores.d")}</p>
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
      <Tabla columnas={columnas} filas={filas} clave={(d) => d.id} />
    </>
  );
}

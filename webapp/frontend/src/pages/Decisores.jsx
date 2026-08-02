import React, { useState } from "react";
import { fmtScore } from "../api.js";
import { Idioma, Ola, Tabla, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { t } from "../i18n/index.js";

export default function Decisores() {
  const { corrida } = useCorrida(getCorridaId());
  const [nivel, setNivel] = useState("");

  const porProspecto = Object.fromEntries((corrida?.prospectos || []).map((p) => [p.id, p]));
  const todos = (corrida?.decisores || []).map((d) => ({ ...d, prospecto: porProspecto[d.prospecto_id] }));
  const filas = nivel ? todos.filter((d) => d.prospecto?.nivel === nivel) : todos;

  const columnas = [
    { id: "score", titulo: t("tabla.score"),
      render: (d) => <b className="tnum" style={{ color: "var(--green-deep)" }}>{fmtScore(d.score)}</b> },
    { id: "ola", titulo: t("tabla.ola"),
      render: (d) => (d.prospecto ? <Ola nivel={d.prospecto.nivel} /> : "—") },
    { id: "decisor", titulo: t("tabla.decisor"),
      // Empresa real → no se inventa la persona: se muestra la búsqueda de
      // LinkedIn armada con el cargo. Sintético → el nombre con su marca.
      render: (d) => (d.nombre
        ? <>{d.nombre} {d.sintetico ? <span className="pill mundo">{t("decisores.sintetico")}</span> : null}</>
        : (d.linkedin
            ? <a href={d.linkedin} target="_blank" rel="noreferrer">{t("decisores.buscar_linkedin")}</a>
            : "—")) },
    { id: "cargo", titulo: t("tabla.cargo"), render: (d) => d.cargo },
    { id: "empresa", titulo: t("tabla.empresa"), render: (d) => d.empresa },
    { id: "pais", titulo: t("tabla.pais"), render: (d) => d.pais },
    { id: "email", titulo: t("tabla.email"),
      // Sin persona identificada se muestra la casilla comercial que la
      // empresa publica en su sitio; si tampoco hay, se explica por qué.
      render: (d) => {
        if (d.email) return d.email;
        const publico = d.prospecto?.contactos?.email;
        if (publico) {
          return <>
            <a href={`mailto:${publico}`}>{publico}</a>{" "}
            <span className="pill mundo">{t("decisores.correo_empresa")}</span>
          </>;
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
          <option value="local">{t("ola.local")}</option>
          <option value="latam">{t("ola.latam")}</option>
          <option value="mundo">{t("ola.mundo")}</option>
        </select>
        <span className="nota" style={{ marginTop: 0 }}>
          {filas.length} {t("common.de")} {todos.length}
        </span>
      </div>
      <Tabla columnas={columnas} filas={filas} clave={(d) => d.id} />
    </>
  );
}

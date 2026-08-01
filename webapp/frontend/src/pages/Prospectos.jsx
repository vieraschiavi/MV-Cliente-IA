import React, { useState } from "react";
import { fmtScore } from "../api.js";
import { Ola, Tabla, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { t } from "../i18n/index.js";

export default function Prospectos() {
  const { corrida } = useCorrida(getCorridaId());
  const [nivel, setNivel] = useState("");

  const todos = corrida?.prospectos || [];
  const filas = nivel ? todos.filter((p) => p.nivel === nivel) : todos;

  const columnas = [
    { id: "score", titulo: t("tabla.score"),
      render: (p) => <b className="tnum" style={{ color: "var(--green-deep)" }}>{fmtScore(p.score)}</b> },
    { id: "ola", titulo: t("tabla.ola"), render: (p) => <Ola nivel={p.nivel} /> },
    { id: "empresa", titulo: t("tabla.empresa"), render: (p) => p.nombre },
    { id: "sector", titulo: t("tabla.sector"), render: (p) => p.sector },
    { id: "pais", titulo: t("tabla.pais"), render: (p) => `${p.pais} · ${p.ciudad}` },
    { id: "empleados", titulo: t("tabla.empleados"),
      render: (p) => <span className="tnum">{p.empleados || "—"}</span> },
    { id: "dominio", titulo: t("tabla.dominio"), render: (p) => p.dominio },
    { id: "senales", titulo: t("tabla.senales"),
      render: (p) => <span style={{ whiteSpace: "normal" }}>{(p.senales || []).join(" · ")}</span> },
  ];

  if (!corrida) return <Vacio />;

  return (
    <>
      <h1 className="page-title">{t("nav.prospectos")}</h1>
      <p className="page-sub">{t("ola.explicacion")}</p>
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
      <Tabla columnas={columnas} filas={filas} clave={(p) => p.id} />
    </>
  );
}

import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Tabla, Vacio } from "../componentes/Comunes.jsx";
import { getCorridaId, setCorridaId } from "../estado.js";
import { t } from "../i18n/index.js";

export default function Historial() {
  const nav = useNavigate();
  const [corridas, setCorridas] = useState(null);
  const [error, setError] = useState("");
  const activa = getCorridaId();

  const traer = useCallback(() => {
    api("/api/corridas")
      .then((d) => setCorridas(d.corridas))
      .catch((e) => { setError(e.message); setCorridas([]); });
  }, []);

  useEffect(traer, [traer]);

  const abrir = (c) => { setCorridaId(c.id); nav("/"); };
  const borrar = async (c) => {
    await api(`/api/corridas/${c.id}`, { metodo: "DELETE" });
    if (c.id === activa) setCorridaId("");
    traer();
  };

  const columnas = [
    { id: "dominio", titulo: t("tabla.dominio"),
      render: (c) => <b>{c.dominio}{c.id === activa ? " ●" : ""}</b> },
    { id: "creada", titulo: t("tabla.creada"),
      render: (c) => (c.creada || "").replace("T", " ").replace("+00:00", " UTC") },
    { id: "modo", titulo: t("tabla.modo"), render: (c) => c.modo },
    { id: "estado", titulo: t("tabla.estado"), render: (c) => t(`estado.${c.estado}`) },
    { id: "prospectos", titulo: t("kpi.prospectos"),
      render: (c) => <span className="tnum">{c.resumen?.prospectos ?? 0}</span> },
    { id: "correos", titulo: t("kpi.correos"),
      render: (c) => <span className="tnum">{c.resumen?.emails ?? 0}</span> },
    { id: "acciones", titulo: t("tabla.acciones"),
      render: (c) => (
        <span style={{ display: "flex", gap: 8 }}>
          <button className="btn ghost" onClick={() => abrir(c)}>{t("historial.abrir")}</button>
          <button className="btn ghost" onClick={() => borrar(c)}>{t("historial.borrar")}</button>
        </span>
      ) },
  ];

  return (
    <>
      <h1 className="page-title">{t("historial.titulo")}</h1>
      <p className="page-sub">{t("historial.subtitulo")}</p>
      {error ? <p className="error-note">{error}</p> : null}
      {corridas === null ? <Vacio texto={t("common.cargando")} />
        : <Tabla columnas={columnas} filas={corridas} clave={(c) => c.id} />}
    </>
  );
}

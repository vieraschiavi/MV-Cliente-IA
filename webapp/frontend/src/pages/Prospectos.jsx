import React, { useState } from "react";
import { fmtScore, urlSegura } from "../api.js";
import { etiquetasOla, Ola, Tabla, Vacio } from "../componentes/Comunes.jsx";
import { Icono } from "../componentes/Iconos.jsx";
import { getCorridaId, useCorrida } from "../estado.js";
import { t } from "../i18n/index.js";

export default function Prospectos() {
  const { corrida } = useCorrida(getCorridaId());
  const [nivel, setNivel] = useState("");
  const [zona, setZona] = useState("");

  const todos = corrida?.prospectos || [];
  const etiquetas = etiquetasOla(corrida);
  const delNivel = nivel ? todos.filter((p) => p.nivel === nivel) : todos;
  const zonas = zonasDe(delNivel);
  // Cambiar de ola puede dejar elegida una zona que ya no está en la lista.
  const zonaVigente = zonas.some((z) => z.valor === zona) ? zona : "";
  const filas = zonaVigente ? delNivel.filter((p) => enZona(p, zonaVigente)) : delNivel;

  const columnas = [
    { id: "score", titulo: t("tabla.score"),
      render: (p) => <b className="tnum" style={{ color: "var(--green-deep)" }}>{fmtScore(p.score)}</b> },
    { id: "ola", titulo: t("tabla.ola"), render: (p) => <Ola nivel={p.nivel} etiquetas={etiquetas} /> },
    { id: "empresa", titulo: t("tabla.empresa"), render: (p) => p.nombre },
    { id: "sector", titulo: t("tabla.sector"), render: (p) => p.sector },
    { id: "pais", titulo: t("tabla.pais"),
      render: (p) => (
        <span title={p.direccion || ""}>
          {p.pais} · {p.ciudad}
          {p.barrio ? <span className="barrio"> · {p.barrio}</span> : null}
        </span>
      ) },
    { id: "empleados", titulo: t("tabla.empleados"),
      render: (p) => <span className="tnum">{p.empleados || "—"}</span> },
    { id: "dominio", titulo: t("tabla.dominio"), render: (p) => p.dominio },
    { id: "contacto", titulo: t("tabla.contacto"),
      // Contactos PÚBLICOS leídos del sitio de la empresa real; los
      // sintéticos no tienen (sus dominios no existen).
      render: (p) => {
        const c = p.contactos || {};
        const enlaces = [
          c.email ? <a key="m" className="con-ico" href={`mailto:${c.email}`} title={c.email}>
            <Icono nombre="sobre" tam={14} /> {c.email}</a> : null,
          c.telefono ? <a key="t" className="con-ico" href={`tel:${c.telefono}`}>
            <Icono nombre="telefono" tam={14} /> {c.telefono}</a> : null,
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
        {zonas.length > 1 ? (
          <select value={zonaVigente} onChange={(e) => setZona(e.target.value)}
                  aria-label={t("tabla.zona")}>
            <option value="">{t("tabla.todas_zonas")}</option>
            {zonas.map((z) => (
              <option key={z.valor} value={z.valor}>
                {/* Ciudad completa también en el barrio: el select cerrado
                    muestra sólo la opción elegida, y «· Solymar» suelto no
                    dice de qué ciudad es. */}
                {z.barrio ? `${z.ciudad} · ${z.barrio}` : z.ciudad} ({z.n})
              </option>
            ))}
          </select>
        ) : null}
        <span className="nota" style={{ marginTop: 0 }}>
          {filas.length} {t("common.de")} {todos.length}
        </span>
      </div>
      <Tabla columnas={columnas} filas={filas} clave={(p) => p.id} />
    </>
  );
}

const SEP = "\u0001";

/** Ciudades (con su cuenta) y, debajo de cada una, sus barrios. */
function zonasDe(prospectos) {
  const ciudades = new Map();
  for (const p of prospectos) {
    if (!p.ciudad) continue;
    const k = `${p.pais}${SEP}${p.ciudad}`;
    const c = ciudades.get(k) || { pais: p.pais, ciudad: p.ciudad, n: 0, barrios: new Map() };
    c.n += 1;
    if (p.barrio) c.barrios.set(p.barrio, (c.barrios.get(p.barrio) || 0) + 1);
    ciudades.set(k, c);
  }
  const salida = [];
  for (const [k, c] of [...ciudades.entries()].sort((a, b) => b[1].n - a[1].n)) {
    salida.push({ valor: k, ciudad: c.ciudad, n: c.n });
    for (const [b, n] of [...c.barrios.entries()].sort((x, y) => y[1] - x[1])) {
      salida.push({ valor: `${k}${SEP}${b}`, ciudad: c.ciudad, barrio: b, n });
    }
  }
  return salida;
}

function enZona(p, valor) {
  const [pais, ciudad, barrio] = valor.split(SEP);
  return p.pais === pais && p.ciudad === ciudad && (!barrio || p.barrio === barrio);
}

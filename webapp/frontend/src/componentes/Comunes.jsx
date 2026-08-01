import React, { useState } from "react";
import { t } from "../i18n/index.js";

/** Etiqueta de color: ola geográfica (local/latam/mundo) o idioma (es/pt/en). */
export function Pill({ tipo, children }) {
  return <span className={`pill ${tipo}`}>{children}</span>;
}

export function Ola({ nivel }) {
  return <Pill tipo={nivel}>{t(`ola.${nivel}`)}</Pill>;
}

export function Idioma({ codigo }) {
  return <Pill tipo={codigo}>{codigo.toUpperCase()}</Pill>;
}

export function Aviso({ children }) {
  return <div className="aviso">⚠️ <span>{children}</span></div>;
}

export function Vacio({ texto }) {
  return <p className="vacio">{texto || t("common.sin_datos")}</p>;
}

/** Botón que copia texto al portapapeles y confirma sin abrir un diálogo. */
export function Copiar({ texto, etiqueta }) {
  const [hecho, setHecho] = useState(false);
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto);
    } catch {
      // El WebView de Android sin permiso de portapapeles y los navegadores
      // sin https caen acá: se usa el camino viejo, que sigue funcionando.
      const ta = document.createElement("textarea");
      ta.value = texto;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setHecho(true);
    setTimeout(() => setHecho(false), 1800);
  };
  return (
    <button className="btn ghost" onClick={copiar}>
      {hecho ? `✓ ${t("common.copiado")}` : etiqueta || t("common.copiar")}
    </button>
  );
}

/**
 * Tabla responsiva. En móvil el CSS la convierte en fichas apiladas y usa
 * `data-col` como etiqueta de cada dato — por eso cada celda lo lleva.
 */
export function Tabla({ columnas, filas, clave }) {
  if (!filas.length) return <Vacio />;
  return (
    <div className="tablewrap">
      <table>
        <thead>
          <tr>{columnas.map((c) => <th key={c.id}>{c.titulo}</th>)}</tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={clave ? clave(f) : i}>
              {columnas.map((c) => (
                <td key={c.id} data-col={c.titulo}>{c.render(f)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Kpis({ items }) {
  return (
    <div className="kpi-grid">
      {items.map((k) => (
        <div className="card kpi" key={k.label}>
          <div className="label">{k.label}</div>
          <div className="value tnum">{k.valor}</div>
          {k.delta ? <div className="delta">{k.delta}</div> : null}
        </div>
      ))}
    </div>
  );
}

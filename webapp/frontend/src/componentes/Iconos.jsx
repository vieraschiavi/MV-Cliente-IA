import React from "react";

/**
 * Iconografía de la aplicación — SVG en línea, un solo trazo, `currentColor`.
 *
 * Antes esto eran emojis (cohete, diana, fichero, engranaje…). Se fueron por
 * tres razones concretas, no por gusto:
 *
 *  1. Un emoji lo dibuja la fuente del SISTEMA, así que el mismo botón se veía
 *     distinto en Windows (Segoe UI Emoji), en el WebView de Android (Noto) y
 *     en el iframe del correo. Una barra lateral con ocho colores ajenos a la
 *     paleta Kobra no es un producto, es un chat.
 *  2. No heredan el color: en `.nav-item.on` el texto se aclara y el emoji se
 *     quedaba igual. Con `currentColor` el icono acompaña el estado (hover,
 *     activo, deshabilitado, verde de éxito, rojo de error) sin una línea de
 *     CSS extra.
 *  3. Van embebidos en el bundle: no hay fuente de iconos ni CDN que buscar,
 *     que es condición para el APK, para Electron y para la edición BAT, que
 *     arrancan sin internet.
 *
 * Todos comparten la misma rejilla de 24 y el mismo grosor de trazo, para que
 * pesen visualmente igual puestos uno al lado del otro. Son decorativos: el
 * texto de al lado es el que nombra la acción, así que van `aria-hidden` y no
 * ensucian al lector de pantalla. Cuando un icono va SOLO (sin texto), se le
 * pasa `titulo` y ahí sí se anuncia.
 */

const TRAZOS = {
  // ---- navegación ----
  brujula: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M15.6 8.4 13.4 13.4 8.4 15.6 10.6 10.6Z" />
    </>
  ),
  diana: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4.8" />
      <circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none" />
    </>
  ),
  ficha: (
    <>
      <rect x="2.6" y="4.6" width="18.8" height="14.8" rx="2.6" />
      <circle cx="8.6" cy="10.4" r="2.1" />
      <path d="M5.2 16.6c.3-1.8 1.7-2.8 3.4-2.8s3.1 1 3.4 2.8" />
      <path d="M14.8 9.6h4.2M14.8 13.2h4.2" />
    </>
  ),
  sobre: (
    <>
      <rect x="2.6" y="5" width="18.8" height="14" rx="2.6" />
      <path d="m3.4 7.6 8.6 5.6 8.6-5.6" />
    </>
  ),
  barras: (
    <>
      <path d="M3.6 20.4h16.8" />
      <path d="M7 20.4v-7.2M12 20.4V5.6M17 20.4v-4.6" />
    </>
  ),
  tendencia: (
    <>
      <path d="m3.6 16.6 5.6-5.6 4 4 7.2-7.2" />
      <path d="M15.6 7.8h4.8v4.8" />
    </>
  ),
  reloj: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.2V12l3 1.9" />
    </>
  ),
  // Deslizadores, no engranaje: la rueda dentada a 18 px se convierte en una
  // mancha, y este menú es justamente el de "ajustar valores".
  ajustes: (
    <>
      <path d="M3.6 7.2h16.8M3.6 12h16.8M3.6 16.8h16.8" />
      <circle cx="9" cy="7.2" r="2.1" fill="currentColor" stroke="none" />
      <circle cx="15.4" cy="12" r="2.1" fill="currentColor" stroke="none" />
      <circle cx="7.6" cy="16.8" r="2.1" fill="currentColor" stroke="none" />
    </>
  ),

  // ---- estado ----
  alerta: (
    <>
      <path d="M12 3.9 21.3 19.6H2.7Z" />
      <path d="M12 10v3.7" />
      <circle cx="12" cy="16.6" r=".95" fill="currentColor" stroke="none" />
    </>
  ),
  chequeo: <path d="m4.8 12.6 4.8 4.8L19.4 7.4" />,
  chequeo_circulo: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.2 2.9 2.9 5.4-5.6" />
    </>
  ),
  equis_circulo: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m9.1 9.1 5.8 5.8M14.9 9.1l-5.8 5.8" />
    </>
  ),
  escudo: (
    <>
      <path d="M12 3.1 20 6.2v5.9c0 4.4-3.3 7.6-8 8.8-4.7-1.2-8-4.4-8-8.8V6.2Z" />
      <path d="m8.6 12 2.6 2.6 4.4-4.6" />
    </>
  ),
  arena: (
    <>
      <path d="M7 3.6h10M7 20.4h10" />
      <path d="M7.6 3.6v3.1c0 2 4.4 4 4.4 5.3s-4.4 3.3-4.4 5.3v3.1" />
      <path d="M16.4 3.6v3.1c0 2-4.4 4-4.4 5.3s4.4 3.3 4.4 5.3v3.1" />
    </>
  ),

  // ---- acciones ----
  descargar: (
    <>
      <path d="M12 3.6v11.2" />
      <path d="m7.6 10.4 4.4 4.4 4.4-4.4" />
      <path d="M4.4 19.6h15.2" />
    </>
  ),
  copiar: (
    <>
      <rect x="8.6" y="8.6" width="11.8" height="11.8" rx="2.4" />
      <path d="M15.4 5.8V5a2.4 2.4 0 0 0-2.4-2.4H6a2.4 2.4 0 0 0-2.4 2.4v7a2.4 2.4 0 0 0 2.4 2.4h.8" />
    </>
  ),
  clip: (
    <>
      <path d="M18.4 10.3 10.5 18.2a4.4 4.4 0 0 1-6.2-6.2l8.6-8.6a2.9 2.9 0 1 1 4.1 4.1l-8.6 8.6a1.45 1.45 0 1 1-2.05-2.05l7.5-7.5" />
    </>
  ),
  enlace_externo: (
    <>
      <path d="M14 4h6v6" />
      <path d="M20 4 11.4 12.6" />
      <path d="M18.2 14v4.4a2.2 2.2 0 0 1-2.2 2.2H5.8a2.2 2.2 0 0 1-2.2-2.2V8.2A2.2 2.2 0 0 1 5.8 6h4.4" />
    </>
  ),
  globo: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3.3 9.6h17.4M3.3 14.4h17.4" />
      <path d="M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18" />
    </>
  ),
  reproducir: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M10.2 8.4 16 12l-5.8 3.6Z" />
    </>
  ),
  rayo: <path d="M13.4 2.6 4.9 13.4h5.9l-.4 8 8.7-11h-5.9Z" />,
  telefono: (
    <path d="M6.3 3.6h3.2l1.6 4-2 1.3a12.6 12.6 0 0 0 6 6l1.3-2 4 1.6v3.2a1.9 1.9 0 0 1-2.1 1.9A16.9 16.9 0 0 1 4.4 5.7a1.9 1.9 0 0 1 1.9-2.1Z" />
  ),
  chevron: <path d="m6.4 9.6 5.6 5.6 5.6-5.6" />,

  // ---- canales ----
  // Marcas genéricas a propósito: al lado siempre va el nombre escrito
  // ("LinkedIn", "Instagram", "TikTok"), así que no hace falta —ni conviene—
  // dibujar el logotipo ajeno.
  maletin: (
    <>
      <rect x="3" y="7.4" width="18" height="12.6" rx="2.4" />
      <path d="M9 7.4V5.9A1.9 1.9 0 0 1 10.9 4h2.2A1.9 1.9 0 0 1 15 5.9v1.5" />
      <path d="M3 12.6h18" />
      <path d="M10.6 12.6h2.8" />
    </>
  ),
  camara: (
    <>
      <rect x="2.8" y="6.8" width="18.4" height="13.2" rx="2.6" />
      <circle cx="12" cy="13.4" r="3.6" />
      <path d="M8.6 6.8 9.8 4h4.4l1.2 2.8" />
    </>
  ),
  musica: (
    <>
      <path d="M9.6 17.4V6.4l10.4-2v11" />
      <circle cx="7" cy="17.4" r="2.6" />
      <circle cx="17.4" cy="15.4" r="2.6" />
    </>
  ),
  equis: <path d="M5.4 5.4 18.6 18.6M18.6 5.4 5.4 18.6" />,
};

export const NOMBRES_ICONO = Object.keys(TRAZOS);

/**
 * @param {string} nombre  clave de `TRAZOS`.
 * @param {number} tam     lado en px (la rejilla es de 24, escala pareja).
 * @param {string} titulo  si el icono va sin texto al lado, lo que se anuncia.
 */
export function Icono({ nombre, tam = 18, titulo = "", className = "" }) {
  const trazo = TRAZOS[nombre];
  // Un nombre mal escrito no puede romper la pantalla entera: se dibuja nada.
  if (!trazo) return null;
  return (
    <svg
      className={`ico-svg${className ? ` ${className}` : ""}`}
      width={tam}
      height={tam}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={titulo ? undefined : "true"}
      role={titulo ? "img" : undefined}
      focusable="false"
    >
      {titulo ? <title>{titulo}</title> : null}
      {trazo}
    </svg>
  );
}

export default Icono;

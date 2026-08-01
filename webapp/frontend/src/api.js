// Cliente HTTP del backend + estado de sesión e idioma.
//
// La base de la API es relativa ("") en web y en el instalador de PC, porque
// el mismo backend sirve el frontend. En el APK no hay backend adentro: el
// WebView tiene que apuntar a un servidor, y la dirección se guarda en
// localStorage (pantalla de Configuración).
const KEY_TOKEN = "mvcliente_token";
const KEY_IDIOMA = "mvcliente_idioma";
const KEY_BASE = "mvcliente_base";

// Capacitor sirve la app desde capacitor://localhost o http://localhost —
// ahí "/api" no existe y hay que pedirle al usuario la dirección del servidor.
export const esNativo = () =>
  typeof window !== "undefined" &&
  (window.location.protocol === "capacitor:" ||
    Boolean(window.Capacitor?.isNativePlatform?.()));

export function getBase() {
  return localStorage.getItem(KEY_BASE) || (esNativo() ? "" : "");
}
export function setBase(url) {
  const limpia = (url || "").trim().replace(/\/+$/, "");
  if (limpia) localStorage.setItem(KEY_BASE, limpia);
  else localStorage.removeItem(KEY_BASE);
}

export function getToken() {
  return localStorage.getItem(KEY_TOKEN) || "";
}
export function setToken(t) {
  if (t) localStorage.setItem(KEY_TOKEN, t);
  else localStorage.removeItem(KEY_TOKEN);
}

export function getIdioma() {
  const guardado = localStorage.getItem(KEY_IDIOMA);
  if (guardado) return guardado;
  // Primer arranque: se respeta el idioma del dispositivo si es uno de los
  // tres del producto; si no, español (el mercado local).
  const nav = (navigator.language || "es").slice(0, 2).toLowerCase();
  return ["es", "pt", "en"].includes(nav) ? nav : "es";
}
export function setIdioma(i) {
  localStorage.setItem(KEY_IDIOMA, i);
}

export class ErrorApi extends Error {
  constructor(mensaje, status) {
    super(mensaje);
    this.status = status;
  }
}

export async function api(ruta, { metodo = "GET", cuerpo, crudo = false } = {}) {
  const token = getToken();
  let r;
  try {
    r = await fetch(getBase() + ruta, {
      method: metodo,
      headers: {
        ...(cuerpo ? { "content-type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch (e) {
    // fetch sólo rechaza por red/CORS: en el APK es el caso habitual cuando
    // la dirección del servidor está mal o el equipo está sin datos.
    throw new ErrorApi(e.message || "sin conexión", 0);
  }
  if (r.status === 401 && ruta !== "/api/auth/login") {
    setToken(null);
    window.location.hash = "#/login";
    throw new ErrorApi("sesion_vencida", 401);
  }
  if (crudo) {
    if (!r.ok) throw new ErrorApi(`Error ${r.status}`, r.status);
    return r;
  }
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new ErrorApi(datos.detail || `Error ${r.status}`, r.status);
  return datos;
}

export async function descargar(ruta, nombre, cuerpo) {
  // Con `cuerpo` se manda la corrida al servidor: es el camino del modo sin
  // estado, donde el backend no la tiene guardada y el archivo hay que
  // armarlo con lo que trae el navegador.
  const r = await api(ruta, cuerpo ? { metodo: "POST", cuerpo, crudo: true }
                                   : { crudo: true });
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Formateo — mismo estándar que MV Kobra AI: score con un decimal, enteros
// con separador de miles.
export const fmtScore = (n) => (Number(n) || 0).toFixed(1);
export const fmtNum = (n, idioma = "es") =>
  Math.round(Number(n) || 0).toLocaleString(idioma === "pt" ? "pt-BR" : idioma === "en" ? "en-US" : "es-UY");

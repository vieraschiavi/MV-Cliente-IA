// Cliente HTTP del backend + estado de sesión e idioma.
//
// La base de la API es relativa ("") en web y en el instalador de PC, porque
// el mismo backend sirve el frontend. En el APK no hay backend adentro: el
// WebView tiene que apuntar a un servidor, y la dirección se guarda en
// localStorage (pantalla de Configuración).
const KEY_TOKEN = "mvcliente_token";
const KEY_IDIOMA = "mvcliente_idioma";
const KEY_BASE = "mvcliente_base";
// La clave de IA que el usuario pega en Configuración. Vive en SU navegador
// y viaja sólo dentro de cada corrida en modo IA: el servidor la usa y la
// descarta — no la guarda ni la escribe en logs. El proveedor dice de quién
// es la clave (Claude, ChatGPT, Gemini o Copilot); el endpoint sólo aplica a
// Copilot/Azure, que no tiene una URL fija.
const KEY_CLAVE_IA = "mvcliente_clave_ia";
const KEY_PROVEEDOR_IA = "mvcliente_proveedor_ia";
const KEY_ENDPOINT_IA = "mvcliente_endpoint_ia";
// Código de dueño del despliegue web: exime del cupo gratis. Se compara en
// el servidor contra la variable MVCLIENTE_OWNER.
const KEY_OWNER = "mvcliente_owner";

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

export function getClaveIA() {
  return localStorage.getItem(KEY_CLAVE_IA) || "";
}
export function setClaveIA(clave) {
  const limpia = (clave || "").trim();
  if (limpia) localStorage.setItem(KEY_CLAVE_IA, limpia);
  else localStorage.removeItem(KEY_CLAVE_IA);
}

export const PROVEEDORES_IA = ["claude", "openai", "gemini", "copilot"];

export function getProveedorIA() {
  const p = localStorage.getItem(KEY_PROVEEDOR_IA) || "claude";
  return PROVEEDORES_IA.includes(p) ? p : "claude";
}
export function setProveedorIA(p) {
  if (p && p !== "claude") localStorage.setItem(KEY_PROVEEDOR_IA, p);
  else localStorage.removeItem(KEY_PROVEEDOR_IA);
}

export function getEndpointIA() {
  return localStorage.getItem(KEY_ENDPOINT_IA) || "";
}
export function setEndpointIA(url) {
  const limpia = (url || "").trim();
  if (limpia) localStorage.setItem(KEY_ENDPOINT_IA, limpia);
  else localStorage.removeItem(KEY_ENDPOINT_IA);
}

export function getOwner() {
  return localStorage.getItem(KEY_OWNER) || "";
}
export function setOwner(codigo) {
  const limpio = (codigo || "").trim();
  if (limpio) localStorage.setItem(KEY_OWNER, limpio);
  else localStorage.removeItem(KEY_OWNER);
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

function cabeceras(cuerpo) {
  const token = getToken();
  const owner = getOwner();
  return {
    ...(cuerpo ? { "content-type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(owner ? { "X-MV-Owner": owner } : {}),
  };
}

export async function api(ruta, { metodo = "GET", cuerpo, crudo = false } = {}) {
  let r;
  try {
    r = await fetch(getBase() + ruta, {
      method: metodo,
      headers: cabeceras(cuerpo),
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

/**
 * POST que va DEVOLVIENDO resultados: el servidor manda una línea JSON por
 * fase (NDJSON) y `onLinea` se llama con cada una — la pantalla pinta
 * empresa, competidores y prospectos a medida que existen, en vez de esperar
 * la corrida entera. Devuelve la última línea (la corrida terminada).
 */
export async function apiStream(ruta, cuerpo, onLinea) {
  let r;
  try {
    r = await fetch(getBase() + ruta, {
      method: "POST",
      headers: cabeceras(cuerpo),
      body: JSON.stringify(cuerpo),
    });
  } catch (e) {
    throw new ErrorApi(e.message || "sin conexión", 0);
  }
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new ErrorApi(d.detail || `Error ${r.status}`, r.status);
  }
  if (!r.body || !r.body.getReader) {
    // Navegador sin streams: cae al comportamiento viejo, todo junto.
    const d = await r.json();
    onLinea(d);
    return d;
  }
  const lector = r.body.getReader();
  const decodificador = new TextDecoder();
  let resto = "";
  let ultima = null;
  for (;;) {
    const { done, value } = await lector.read();
    if (done) break;
    resto += decodificador.decode(value, { stream: true });
    let corte;
    while ((corte = resto.indexOf("\n")) >= 0) {
      const linea = resto.slice(0, corte).trim();
      resto = resto.slice(corte + 1);
      if (!linea) continue;
      try {
        ultima = JSON.parse(linea);
        onLinea(ultima);
      } catch {
        // línea partida o basura: se ignora, la siguiente completa trae todo
      }
    }
  }
  return ultima;
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

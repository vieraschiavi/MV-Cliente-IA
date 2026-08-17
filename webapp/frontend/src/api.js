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
// El modelo elegido y la última lista traída del proveedor, UNO POR
// PROVEEDOR (a diferencia de la clave, que es una sola activa a la vez):
// así cambiar de proveedor y volver no hace perder lo que ya se eligió ni
// obliga a apretar "Actualizar" de nuevo. `{claude: {modelo, modelos,
// actualizado}, openai: {...}, …}`.
const KEY_MODELOS_IA = "mvcliente_modelos_ia";
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

// El candado de texto plano que Android Network Security Config NO puede
// hacer (no entiende rangos de IP). En el APK el servidor se apunta a mano, y
// las claves del usuario (modelo, SMTP, X, LinkedIn) viajan en cada pedido:
// permitir `http://` a un host PÚBLICO las dejaría a la vista de cualquiera en
// el mismo wifi. `https://` siempre pasa; `http://` sólo a loopback o a una
// red privada (RFC 1918), que es donde vive un servidor propio en la LAN.
export function baseInsegura(base) {
  const u = (base || "").trim();
  if (!u || /^https:\/\//i.test(u)) return false;      // vacío o https: ok
  if (!/^http:\/\//i.test(u)) return false;            // no es http(s): no aplica
  let host;
  try { host = new URL(u).hostname.toLowerCase(); } catch { return true; }
  const priv = /^(localhost|127\.\d+\.\d+\.\d+|::1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)$/;
  return !priv.test(host);                              // http a host público = inseguro
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

export const PROVEEDORES_IA = ["claude", "openai", "gemini", "copilot", "grok"];
// Copilot no entra: en Azure el modelo lo fija el deployment de la URL del
// endpoint, no hay lista que traer (cliente_ia/proveedores/llm.py).
export const PROVEEDORES_CON_LISTA_DE_MODELOS = ["claude", "openai", "gemini", "grok"];

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

function _modelosIA() {
  try {
    return JSON.parse(localStorage.getItem(KEY_MODELOS_IA)) || {};
  } catch {
    return {};
  }
}
function _guardarModelosIA(datos) {
  localStorage.setItem(KEY_MODELOS_IA, JSON.stringify(datos));
}

// El modelo puntual elegido para regular el consumo de tokens (p. ej.
// "claude-haiku-4-5" en vez del default del servidor). Vacío = default.
export function getModeloIA(proveedor) {
  return _modelosIA()[proveedor]?.modelo || "";
}
export function setModeloIA(proveedor, modelo) {
  const todos = _modelosIA();
  todos[proveedor] = { ...todos[proveedor], modelo: (modelo || "").trim() };
  _guardarModelosIA(todos);
}

// La última lista de modelos que devolvió la API del proveedor (botón
// «Actualizar»), en caché para no tener que volver a pedirla cada vez que
// se abre Configuración.
export function getModelosDisponibles(proveedor) {
  return _modelosIA()[proveedor]?.modelos || [];
}
export function getModelosActualizado(proveedor) {
  return _modelosIA()[proveedor]?.actualizado || "";
}
export function setModelosDisponibles(proveedor, modelos) {
  const todos = _modelosIA();
  todos[proveedor] = { ...todos[proveedor], modelos,
                       actualizado: new Date().toISOString() };
  _guardarModelosIA(todos);
}

// Le pregunta al servidor (que a su vez le pregunta al proveedor con esta
// clave) qué modelos hay disponibles ahora mismo. La clave viaja sólo en
// esta petición, igual que en una corrida.
export function listarModelosIA(proveedor, clave) {
  return api("/api/ia/modelos", { metodo: "POST", cuerpo: { proveedor, clave } });
}

// Correo del usuario para las búsquedas reales gratis de la web: el servidor
// lo pide para contar el cupo (y el del dueño no descuenta).
const KEY_EMAIL = "mvcliente_email";

export function getEmail() {
  return localStorage.getItem(KEY_EMAIL) || "";
}
export function setEmail(correo) {
  const limpio = (correo || "").trim();
  if (limpio) localStorage.setItem(KEY_EMAIL, limpio);
  else localStorage.removeItem(KEY_EMAIL);
}

// Configuración SMTP para el envío real de correos. Vive en el navegador del
// usuario; las credenciales viajan sólo dentro de cada envío y el servidor
// las usa y las descarta (misma política que la clave de IA).
const KEY_SMTP = "mvcliente_smtp";

export function getSmtp() {
  try {
    return JSON.parse(localStorage.getItem(KEY_SMTP)) || null;
  } catch {
    return null;
  }
}
export function setSmtp(cfg) {
  if (cfg && cfg.host && cfg.usuario) localStorage.setItem(KEY_SMTP, JSON.stringify(cfg));
  else localStorage.removeItem(KEY_SMTP);
}

// Claves de la API de X (developer.x.com) para publicar el post de campaña
// desde «Automatizar flujo». Misma política que el SMTP: viven en ESTE
// navegador y viajan sólo con la petición que las usa.
const KEY_X = "mvcliente_x";

export function getX() {
  try {
    return JSON.parse(localStorage.getItem(KEY_X)) || null;
  } catch {
    return null;
  }
}
export function setX(cfg) {
  if (cfg && cfg.consumer_key && cfg.access_token) {
    localStorage.setItem(KEY_X, JSON.stringify(cfg));
  } else localStorage.removeItem(KEY_X);
}

// Proveedor de LinkedIn del usuario (ver cliente_ia/redes.py: LinkedIn no
// expone API pública de mensajes, así que se pasa por el proveedor que él
// contrató). Mismas reglas que el SMTP: vive acá, viaja sólo con la petición.
const KEY_LI = "mvcliente_linkedin";

export function getLinkedIn() {
  try {
    return JSON.parse(localStorage.getItem(KEY_LI)) || null;
  } catch {
    return null;
  }
}
export function setLinkedIn(cfg) {
  if (cfg && cfg.dsn && cfg.api_key && cfg.account_id) {
    localStorage.setItem(KEY_LI, JSON.stringify(cfg));
  } else localStorage.removeItem(KEY_LI);
}

// Historial de automatizaciones: qué se mandó, a quién y cómo salió. Vive en
// ESTE dispositivo a propósito — en Vercel el backend es sin estado (no hay
// disco que sobreviva a la respuesta), así que un historial servidor no
// existiría en el despliegue web. Acá anda igual en web, PC y APK.
const KEY_ENVIOS = "mvcliente_envios";
const TOPE_ENVIOS = 200;

export function getEnvios() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY_ENVIOS));
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}
export function agregarEnvio(registro) {
  const previos = getEnvios();
  // El más nuevo primero y con tope: sin el corte, un usuario que automatiza
  // todos los días termina llenando localStorage y la app deja de guardar.
  const nuevos = [registro, ...previos].slice(0, TOPE_ENVIOS);
  localStorage.setItem(KEY_ENVIOS, JSON.stringify(nuevos));
  return nuevos;
}
export function borrarEnvios() {
  localStorage.removeItem(KEY_ENVIOS);
}

// Métricas de envíos y conversión del BACKEND (cliente_ia/metricas.py). A
// diferencia del historial de arriba —que vive en este dispositivo— esto se
// guarda en el servidor y cruza envíos con conversiones para decir a qué
// segmento, día y hora le fue mejor. `registrarEnvios` es best-effort: si el
// servidor no está, la automatización no se cae por no poder registrar.
export function registrarEnvios(eventos) {
  if (!eventos || !eventos.length) return Promise.resolve(null);
  return api("/api/metricas/envios", { metodo: "POST", cuerpo: { eventos } })
    .catch(() => null);
}
export function resumenMetricas(programa = "", costo = null) {
  const q = new URLSearchParams();
  if (programa) q.set("programa", programa);
  if (costo != null && costo !== "") q.set("costo", String(costo));
  const cola = q.toString();
  return api("/api/metricas/resumen" + (cola ? `?${cola}` : ""));
}

// Estado de la licencia del programa instalado. En la web devuelve
// {aplica:false}: ahí manda el cupo gratis, no una licencia.
export async function getLicencia() {
  try {
    return await api("/api/licencia");
  } catch {
    return { aplica: false, edicion: "?" };
  }
}
export function activarLicencia(clave) {
  return api("/api/licencia", { metodo: "POST", cuerpo: { clave } });
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

/**
 * La URL si se puede navegar a ella sin peligro; `undefined` si no.
 *
 * Todo lo que termina en un `href` de la app viene de afuera: el video y la
 * landing los escribe quien lanza la corrida, y LinkedIn/Instagram/teléfono
 * salen de rastrear sitios ajenos. React NO frena `javascript:` en un href
 * (avisa por consola y lo deja pasar), así que un `javascript:fetch(...)`
 * ahí se ejecuta con el origen de la app y se lleva el localStorage —
 * claves de SMTP, del modelo, de X y de LinkedIn.
 *
 * Un `href` sin valor hace que React no emita el atributo: el enlace queda
 * muerto, que es exactamente lo que se busca.
 */
export function urlSegura(u) {
  if (!u || typeof u !== "string") return undefined;
  try {
    // `new URL` con base resuelve también las relativas sin romperse.
    const p = new URL(u, window.location.origin).protocol;
    return ["http:", "https:", "mailto:", "tel:"].includes(p) ? u : undefined;
  } catch {
    return undefined;                       // ni siquiera es una URL
  }
}

export class ErrorApi extends Error {
  constructor(mensaje, status) {
    super(mensaje);
    this.status = status;
  }
}

/**
 * En el APK, sin dirección configurada, `fetch("" + ruta)` es una URL
 * RELATIVA — se resuelve contra el propio origen de la app
 * (`https://localhost`), que es donde Capacitor sirve el bundle. Su servidor
 * local está en "html5mode" (rutea cualquier ruta sin extensión a
 * `index.html`, para que el router de una sola página funcione en `/#/...`),
 * así que `/api/salud` no daba un error de red: devolvía el propio HTML de
 * la app con status 200. `r.json()` fallaba en silencio (hay un `.catch(()
 * => ({}))` para no romper con una respuesta vacía) y `api()` devolvía `{}`
 * como si el pedido hubiera funcionado — "Conexión correcta" con
 * `r.version` en `undefined`. Un falso positivo: nunca se habló con ningún
 * servidor.
 *
 * Se corta ACÁ, antes del fetch, con el mismo criterio que `baseInsegura`:
 * en native sin base no hay adónde ir. `sin import de i18n/index.js` a
 * propósito — ese módulo importa `getIdioma`/`setIdioma` DESDE este archivo,
 * así que importar `t()` acá cerraría un ciclo. El texto va en las tres
 * lenguas, a mano, como en `cliente_ia/redaccion.py` del lado del motor.
 */
const FALTA_SERVIDOR = {
  es: "Configurá la dirección del servidor en Ajustes antes de buscar.",
  pt: "Configure o endereço do servidor em Configurações antes de buscar.",
  en: "Set the server address in Settings before searching.",
};

function faltaServidor() {
  return esNativo() && !getBase();
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
  // Sin base en el APK, "" + ruta es relativa a https://localhost — que
  // Capacitor responde con su propio index.html (ver el comentario de
  // FALTA_SERVIDOR más arriba). Cortar acá evita el falso "conexión
  // correcta".
  if (faltaServidor()) {
    throw new ErrorApi(FALTA_SERVIDOR[getIdioma()] || FALTA_SERVIDOR.es, 0);
  }
  // Ningún pedido en texto plano a un host público: llevaría las claves del
  // usuario a la vista de cualquiera en la misma red. Se corta antes del
  // fetch, no después.
  if (baseInsegura(getBase())) {
    throw new ErrorApi("servidor_inseguro_http", 0);
  }
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
  if (faltaServidor()) {
    throw new ErrorApi(FALTA_SERVIDOR[getIdioma()] || FALTA_SERVIDOR.es, 0);
  }
  if (baseInsegura(getBase())) {
    throw new ErrorApi("servidor_inseguro_http", 0);
  }
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

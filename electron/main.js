/*
 * MV Cliente IA · app de escritorio (Electron)
 * =============================================
 * Proceso principal: levanta el backend (FastAPI + el build de React) en un
 * puerto libre de 127.0.0.1 y abre la ventana apuntando ahí. Es la MISMA
 * interfaz que corre en la nube, pero como PROGRAMA de PC: el motor corre en
 * tu máquina, los datos no salen. No abre el navegador ni la web.
 *
 * Empaquetado, el backend viaja como ejecutable de PyInstaller en
 * resources/backend/. En desarrollo (`npm start` dentro de electron/) se
 * levanta desde el código fuente con el Python del sistema.
 *
 * Igual que en MV Kobra AI se desactiva la aceleración por GPU: la
 * compositación de Chromium se pelea con OBS, el escritorio remoto y algunos
 * drivers viejos, y la ventana queda toda gris. Es un tablero de React, así
 * que por CPU se ve igual. Se puede volver a activar con MVCLIENTE_GPU=1.
 */
const { app, BrowserWindow, Menu, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const net = require("net");
const path = require("path");
const fs = require("fs");
const os = require("os");

if (process.env.MVCLIENTE_GPU !== "1") {
  app.disableHardwareAcceleration();
  app.commandLine.appendSwitch("disable-gpu-compositing");
}

const ESPERA_BACKEND_MS = 90_000;   // el primer arranque instalado carga el catálogo
let ventana = null;
let splash = null;
let backend = null;
let cerrando = false;
let flujoLog = null;

// --- Log en disco --------------------------------------------------------
// Cuando el motor no arranca en la máquina del usuario (lo típico: el
// antivirus pone en cuarentena el .exe del motor, que va sin firma), hay que
// poder ver POR QUÉ. Todo lo que escupe el motor y cada paso del arranque
// quedan en un archivo que el usuario puede mandar.
function rutaLog() {
  const dir = app.isPackaged
    ? (dirDatos() || path.join(os.tmpdir(), "MVClienteIA"))
    : os.tmpdir();
  try { fs.mkdirSync(dir, { recursive: true }); } catch { /* ya existe */ }
  return path.join(dir, "mvclienteia.log");
}

function log(linea) {
  const texto = `[${new Date().toISOString()}] ${linea}\n`;
  process.stdout.write(texto);
  try {
    if (!flujoLog) flujoLog = fs.createWriteStream(rutaLog(), { flags: "a" });
    flujoLog.write(texto);
  } catch { /* si no se puede escribir el log, no es fatal */ }
}

function puertoLibre() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function esperarBackend(url, timeoutMs) {
  const inicio = Date.now();
  return new Promise((resolve, reject) => {
    const intentar = () => {
      const req = http.get(url, (res) => { res.resume(); resolve(); });
      req.on("error", () => {
        if (Date.now() - inicio > timeoutMs) {
          reject(new Error("El motor no respondió a tiempo"));
        } else {
          setTimeout(intentar, 350);
        }
      });
    };
    intentar();
  });
}

/**
 * Dónde guardar corridas y exports. Si la carpeta de la app es escribible
 * (edición portable descomprimida en D:\, o instalación por usuario), los
 * datos van AL LADO de la app: todo queda en el disco que eligió el usuario.
 * Si no se puede escribir ahí (p. ej. instalada en Archivos de programa),
 * el motor cae solo a la carpeta de datos del usuario.
 */
function dirDatos() {
  if (!app.isPackaged) return null;                 // en desarrollo manda el repo
  const candidato = path.join(path.dirname(process.execPath), "datos");
  try {
    fs.mkdirSync(candidato, { recursive: true });
    const prueba = path.join(candidato, ".escritura");
    fs.writeFileSync(prueba, "ok");
    fs.unlinkSync(prueba);
    return candidato;
  } catch {
    return null;
  }
}

// Carpetas de Chromium que NO se copian al mudar el perfil: son caché
// regenerable y pesan más que todo lo demás junto.
const CACHES = new Set(["Cache", "Code Cache", "GPUCache", "DawnCache",
                        "DawnGraphiteCache", "DawnWebGPUCache", "ShaderCache",
                        "GrShaderCache", "blob_storage", "Crashpad"]);

/**
 * El perfil del WebView, al lado de la app — para que elegir el disco sirva.
 *
 * El instalador deja elegir carpeta (y disco), y `dirDatos()` ya manda las
 * corridas y los exports ahí. Pero el PERFIL de Chromium —el localStorage,
 * donde viven la clave de licencia, la del modelo, la del SMTP y las de X y
 * LinkedIn— seguía yéndose a `%APPDATA%`, o sea a C:, siempre. Instalar en D:
 * dejaba la mitad del programa en C: igual, que es justo lo que el usuario
 * quería evitar.
 *
 * Tres cuidados:
 *
 * 1. Sólo se muda si la carpeta de la app es ESCRIBIBLE. Si no lo es, se deja
 *    el perfil donde estaba: un perfil que no se puede escribir es una app que
 *    no arranca.
 * 2. La migración COPIA, no mueve. Si algo sale mal, la configuración vieja
 *    sigue intacta en su lugar de siempre y el usuario, en el peor caso, la
 *    vuelve a cargar — no la pierde.
 * 3. Se llama ANTES de `app.whenReady()`: después de que Chromium abrió el
 *    perfil, `setPath` no tiene efecto.
 */
function perfilJuntoALaApp() {
  const dir = dirDatos();
  if (!dir) return;                       // Program Files o similar: no se toca
  const destino = path.join(dir, "perfil");
  const original = app.getPath("userData");
  try {
    if (!fs.existsSync(destino) && fs.existsSync(original)) {
      fs.cpSync(original, destino, {
        recursive: true,
        filter: (origen) => !CACHES.has(path.basename(origen)),
      });
      log(`perfil migrado de ${original} a ${destino}`);
    }
    app.setPath("userData", destino);
  } catch (e) {
    // Sin perfil junto a la app se sigue con el de siempre: se pierde la
    // portabilidad, no el programa.
    log(`no se pudo mudar el perfil (${e.message}); se usa ${original}`);
  }
}

/** Ejecutable empaquetado si existe; si no, el código fuente con Python. */
function comandoBackend(puerto) {
  const empaquetado = path.join(
    process.resourcesPath || "",
    "backend",
    process.platform === "win32" ? "MVClienteIA.exe" : "MVClienteIA"
  );
  if (fs.existsSync(empaquetado)) {
    return { cmd: empaquetado, args: ["--puerto", String(puerto)], cwd: path.dirname(empaquetado) };
  }
  const raiz = path.join(__dirname, "..");
  const python = process.platform === "win32" ? "python" : "python3";
  return {
    cmd: python,
    args: ["-m", "uvicorn", "webapp.backend.api:app", "--host", "127.0.0.1", "--port", String(puerto)],
    cwd: raiz,
    esFuente: true,
  };
}

/** Pantalla de carga inmediata: apenas se abre la app se ve que ES un
 *  programa que está arrancando, no una ventana que nunca aparece. */
function abrirSplash() {
  splash = new BrowserWindow({
    width: 460, height: 300, frame: false, resizable: false, center: true,
    backgroundColor: "#0a1020", title: "MV Cliente IA", show: true,
    icon: path.join(__dirname, "build", process.platform === "win32" ? "icon.ico" : "icon.png"),
  });
  const html =
    "<!doctype html><meta charset=utf-8>" +
    "<body style='margin:0;height:100vh;display:flex;flex-direction:column;" +
    "align-items:center;justify-content:center;background:#0a1020;color:#e7edf5;" +
    "font-family:Segoe UI,system-ui,sans-serif;gap:14px'>" +
    "<div style='font-size:26px;font-weight:800;letter-spacing:.5px'>MV CLIENTE " +
    "<span style='color:#7cc242'>IA</span></div>" +
    "<div style='opacity:.8'>Iniciando el motor en tu equipo…</div>" +
    "<div style='width:180px;height:4px;border-radius:4px;overflow:hidden;background:#1a2740'>" +
    "<div style='width:40%;height:100%;background:#00c896;animation:m 1.1s ease-in-out infinite'></div></div>" +
    "<style>@keyframes m{0%{margin-left:-40%}100%{margin-left:100%}}</style></body>";
  splash.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(html));
  splash.on("closed", () => { splash = null; });
}

function cerrarSplash() {
  if (splash && !splash.isDestroyed()) splash.close();
  splash = null;
}

/** Mensaje de falla accionable: la causa nº1 en Windows es el antivirus
 *  poniendo en cuarentena el motor sin firma. Se dice, y se apunta al log. */
function fallar(mensaje) {
  cerrarSplash();
  const detalle =
    `${mensaje}\n\n` +
    "MV Cliente IA ejecuta un motor propio en tu equipo (no abre la web). " +
    "Si no arranca, casi siempre es el antivirus o Windows Defender bloqueando " +
    "el motor, que va sin firma de código.\n\n" +
    "Qué probar:\n" +
    "• Permitir «MVClienteIA» en el antivirus / Windows Defender y abrir de nuevo.\n" +
    "• Usar la edición Portable (ZIP) descomprimida en un disco tuyo (D:\\).\n\n" +
    `Detalle técnico para soporte: ${rutaLog()}`;
  dialog.showErrorBox("MV Cliente IA — no se pudo iniciar el motor", detalle);
}

/**
 * Menú nativo de Windows. Un programa de escritorio de verdad tiene barra de
 * menú, atajos y un "Acerca de" — sin eso la ventana se siente una página web
 * metida en un marco. Nada de DevTools ni recargas de navegador a la vista:
 * lo que hay son acciones del PRODUCTO.
 */
function menuNativo(url) {
  const plantilla = [
    {
      label: "&Archivo",
      submenu: [
        {
          label: "Nueva búsqueda",
          accelerator: "CmdOrCtrl+N",
          click: () => { if (ventana) ventana.loadURL(url); },
        },
        {
          label: "Abrir carpeta de datos",
          click: () => {
            const dir = dirDatos();
            if (dir) shell.openPath(dir);
            else dialog.showMessageBox(ventana, {
              type: "info", title: "MV Cliente IA",
              message: "Las corridas y los exports se guardan en la carpeta de datos de tu usuario.",
            });
          },
        },
        { type: "separator" },
        { label: "Salir", accelerator: "Alt+F4", role: "quit" },
      ],
    },
    {
      label: "&Ver",
      submenu: [
        { label: "Actualizar", accelerator: "F5", role: "reload" },
        { type: "separator" },
        { label: "Acercar", accelerator: "CmdOrCtrl+Plus", role: "zoomIn" },
        { label: "Alejar", accelerator: "CmdOrCtrl+-", role: "zoomOut" },
        { label: "Tamaño normal", accelerator: "CmdOrCtrl+0", role: "resetZoom" },
        { type: "separator" },
        { label: "Pantalla completa", accelerator: "F11", role: "togglefullscreen" },
      ],
    },
    {
      label: "A&yuda",
      submenu: [
        {
          label: "Ver registro de arranque",
          click: () => shell.openPath(rutaLog()),
        },
        {
          label: "Sitio del producto",
          click: () => shell.openExternal("https://mv-cliente-ia.vercel.app"),
        },
        { type: "separator" },
        {
          label: "Acerca de MV Cliente IA",
          click: () => dialog.showMessageBox(ventana, {
            type: "info",
            title: "Acerca de MV Cliente IA",
            message: `MV Cliente IA ${app.getVersion()}`,
            detail:
              "Encontrá tus próximos clientes: investiga tu producto, mapea la " +
              "competencia, busca compradores, ubica decisores y escribe los correos.\n\n" +
              "El motor corre en esta computadora — tus datos no salen de acá.\n" +
              `Datos: ${dirDatos() || "carpeta de datos del usuario"}`,
            buttons: ["Cerrar"],
          }),
        },
      ],
    },
  ];
  return Menu.buildFromTemplate(plantilla);
}

async function arrancar(intento = 0) {
  const puerto = await puertoLibre();
  const { cmd, args, cwd, esFuente } = comandoBackend(puerto);
  log(`intento ${intento}: ${cmd} ${args.join(" ")}`);

  let listo = false;
  // Si el motor muere ANTES de responder /api/salud (lo típico: otra app le
  // ganó el puerto entre que lo sondeamos y que uvicorn hizo bind), no tiene
  // sentido esperar los 90 s del timeout: se corta al instante y se reintenta
  // con un puerto nuevo.
  let avisarMuerte = () => {};
  const muerteTemprana = new Promise((_, reject) => {
    avisarMuerte = (code) => reject(new Error(`el motor terminó (código ${code}) antes de arrancar`));
  });

  let errorSpawn = null;
  try {
    backend = spawn(cmd, args, {
      cwd,
      windowsHide: true,
      // El backend escucha SÓLO en 127.0.0.1, así que no hace falta contraseña
      // para hablar con tu propia máquina (ver el docstring de webapp/backend).
      env: {
        ...process.env,
        MVCLIENTE_PUERTO: String(puerto),
        PYTHONUNBUFFERED: "1",
        ...(dirDatos() ? { MVCLIENTE_DIR_DATOS: dirDatos() } : {}),
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (e) {
    errorSpawn = e;
  }

  if (errorSpawn || !backend) {
    // spawn falló de entrada: el .exe del motor no está o el SO no lo dejó
    // ejecutar (antivirus). Con código fuente sin Python es el caso esperado.
    log(`spawn falló: ${errorSpawn ? errorSpawn.message : "sin proceso"}`);
    fallar(esFuente
      ? "No se encontró Python para el modo desarrollo."
      : "El sistema no permitió ejecutar el motor (MVClienteIA.exe).");
    app.quit();
    return;
  }

  backend.on("error", (e) => { log(`error del proceso motor: ${e.message}`); avisarMuerte(-1); });
  backend.stdout.on("data", (d) => log(`[motor] ${String(d).trimEnd()}`));
  backend.stderr.on("data", (d) => log(`[motor] ${String(d).trimEnd()}`));
  backend.on("exit", (code) => {
    log(`el motor salió con código ${code}`);
    if (!listo) { avisarMuerte(code); return; }
    // Si el motor se muere solo, la ventana queda mostrando una página que ya
    // no responde: es peor que decirlo.
    if (!cerrando && code !== 0) {
      dialog.showErrorBox("MV Cliente IA",
        `El motor se detuvo (código ${code}). Cerrá la aplicación y volvé a abrirla.`);
    }
  });

  const url = `http://127.0.0.1:${puerto}/`;
  try {
    await Promise.race([
      esperarBackend(`${url}api/salud`, ESPERA_BACKEND_MS),
      muerteTemprana,
    ]);
    listo = true;
    log(`motor listo en ${url}`);
  } catch (e) {
    log(`no arrancó: ${e.message}`);
    if (backend && !backend.killed) backend.kill();
    if (intento < 2) {
      return arrancar(intento + 1);        // puerto nuevo, motor nuevo
    }
    fallar(`No se pudo iniciar el motor: ${e.message}`);
    app.quit();
    return;
  }

  ventana = new BrowserWindow({
    width: 1400, height: 940, minWidth: 900, minHeight: 620,
    backgroundColor: "#0a1020",
    title: "MV Cliente IA",
    show: false,
    icon: path.join(__dirname, "build", process.platform === "win32" ? "icon.ico" : "icon.png"),
    webPreferences: { contextIsolation: true, nodeIntegration: false,
                      preload: path.join(__dirname, "preload.js") },
  });
  Menu.setApplicationMenu(menuNativo(url));
  // Los enlaces externos (un sitio de prospecto) van al navegador del sistema,
  // no reemplazan la ventana de la app.
  //
  // El esquema se valida ANTES de entregarle nada a `shell.openExternal`, que
  // es el manejador de URIs de Windows: con una URL cruda, un `file://` a un
  // recurso de red o un `ms-msdt:`/`search-ms:` dejaban de ser un enlace roto
  // y pasaban a ser ejecución. Y estas URLs no son nuestras — el video y la
  // landing los escribe quien lanza la corrida, y los perfiles salen de
  // rastrear sitios ajenos.
  ventana.webContents.setWindowOpenHandler(({ url: destino }) => {
    try {
      const protocolo = new URL(destino).protocol;
      if (protocolo === "https:" || protocolo === "http:") shell.openExternal(destino);
      else log(`enlace externo bloqueado (esquema ${protocolo})`);
    } catch {
      log("enlace externo bloqueado (no es una URL)");
    }
    return { action: "deny" };
  });
  // La ventana no tiene barra de direcciones: si algo lograra navegarla a otro
  // origen, el usuario vería una página ajena con el marco de "MV Cliente IA"
  // — el escenario ideal para pedirle la clave de licencia o la del correo.
  // Sólo se navega dentro del propio motor.
  ventana.webContents.on("will-navigate", (evento, destino) => {
    try {
      if (new URL(destino).origin !== new URL(url).origin) {
        evento.preventDefault();
        log(`navegación bloqueada hacia ${new URL(destino).origin}`);
      }
    } catch {
      evento.preventDefault();
    }
  });
  // Electron concede los permisos que le pidan si nadie contesta. La app no
  // usa cámara, micrófono ni ubicación: se niegan todos, en bloque.
  ventana.webContents.session.setPermissionRequestHandler((_wc, permiso, responder) => {
    log(`permiso denegado: ${permiso}`);
    responder(false);
  });
  // La ventana real recién se muestra cuando la app ya está pintada: se pasa
  // del splash directo al tablero, sin un parpadeo en blanco.
  ventana.once("ready-to-show", () => { cerrarSplash(); ventana.show(); });
  ventana.on("closed", () => { ventana = null; });
  await ventana.loadURL(url);
}

// Antes de `whenReady`: una vez que Chromium abrió el perfil, `setPath` ya no
// tiene efecto y el programa quedaría a medias entre dos discos.
perfilJuntoALaApp();

app.whenReady().then(() => {
  log(`arranque · empaquetado=${app.isPackaged} · plataforma=${process.platform}`
      + ` · datos=${dirDatos() || "carpeta del usuario"}`);
  abrirSplash();
  arrancar().catch((e) => { log(`fallo inesperado: ${e.stack || e}`); fallar(String(e)); app.quit(); });
});

app.on("window-all-closed", () => { app.quit(); });

app.on("before-quit", () => {
  cerrando = true;
  if (backend && !backend.killed) backend.kill();
  if (flujoLog) { try { flujoLog.end(); } catch { /* nada */ } }
});

/*
 * MV Cliente IA · humo de la app de escritorio
 * =============================================
 * Levanta el motor y abre una ventana de Electron con la MISMA configuración
 * que `electron/main.js`, comprueba que la interfaz pintó de verdad y saca una
 * captura como prueba.
 *
 * Por qué existe: el instalador de Windows se verifica en el CI de Windows
 * (packaging/humo.py, por HTTP), pero eso prueba el MOTOR — no prueba que la
 * ventana de Electron abra y renderice. Cuando se subió Electron de la 33 a la
 * 43 no había forma de contestar "¿sigue andando la ventana?" sin una máquina
 * Windows a mano. Esto corre en Linux headless (xvfb) y contesta esa pregunta
 * en segundos, así que una actualización de Electron deja de ser un salto de fe.
 *
 * No reemplaza al CI de Windows: no prueba el instalador NSIS, ni el
 * desinstalador, ni el .exe de PyInstaller. Prueba la capa Electron.
 *
 *     xvfb-run -a node packaging/humo_electron.js
 *     xvfb-run -a node packaging/humo_electron.js --captura /tmp/app.png
 *
 * Sale 0 si todo bien, 1 con el motivo si algo falló.
 */
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const net = require("net");
const path = require("path");
const fs = require("fs");

const RAIZ = path.join(__dirname, "..");
const ESPERA_MS = 60_000;
// Los ocho destinos de la barra lateral (webapp/frontend/src/App.jsx:NAV).
const DESTINOS = 8;

const args = process.argv.slice(2);
const rutaCaptura = args.includes("--captura")
  ? args[args.indexOf("--captura") + 1]
  : null;

const fallas = [];
let motor = null;

function log(m) { process.stdout.write(`  ${m}\n`); }

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

function esperar(url) {
  const inicio = Date.now();
  return new Promise((resolve, reject) => {
    const intentar = () => {
      const req = http.get(url, (res) => { res.resume(); resolve(); });
      req.on("error", () => {
        if (Date.now() - inicio > ESPERA_MS) reject(new Error("el motor no respondió"));
        else setTimeout(intentar, 300);
      });
    };
    intentar();
  });
}

async function correr() {
  log(`Electron ${process.versions.electron} · Chromium ${process.versions.chrome} · Node ${process.versions.node}`);

  const puerto = await puertoLibre();
  motor = spawn("python3",
    ["-m", "uvicorn", "webapp.backend.api:app", "--host", "127.0.0.1",
     "--port", String(puerto), "--log-level", "warning"],
    { cwd: RAIZ, stdio: ["ignore", "ignore", "pipe"] });
  const url = `http://127.0.0.1:${puerto}/`;
  await esperar(`${url}api/salud`);
  log(`motor arriba en ${url}`);

  // Misma configuración que electron/main.js: si un endurecimiento de Electron
  // rompiera `contextIsolation` o el preload, tiene que romperse ACÁ.
  const ventana = new BrowserWindow({
    width: 1400, height: 940, show: false,
    backgroundColor: "#0a1020",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(RAIZ, "electron", "preload.js"),
    },
  });

  const errores = [];
  ventana.webContents.on("console-message", (_e, nivel, mensaje) => {
    // nivel 3 = error. Un error de consola en el arranque es un bug real.
    if (nivel >= 3) errores.push(mensaje);
  });
  ventana.webContents.on("render-process-gone", (_e, d) =>
    fallas.push(`el proceso de render murió: ${d.reason}`));

  await ventana.loadURL(url);
  // El tablero pide /api/auth/estado y /api/geo antes de pintar la barra.
  await new Promise((r) => setTimeout(r, 2500));

  // --- comprobaciones -----------------------------------------------------
  const visto = await ventana.webContents.executeJavaScript(`(() => ({
    destinos: document.querySelectorAll('.nav-item').length,
    iconos: document.querySelectorAll('svg.ico-svg').length,
    colapsados: [...document.querySelectorAll('svg.ico-svg')]
      .filter(s => { const r = s.getBoundingClientRect();
                     return r.width < 8 || r.height < 8; }).length,
    puente: typeof window.mvClienteIA === 'object' && window.mvClienteIA.escritorio === true,
    nodeExpuesto: typeof window.require !== 'undefined' || typeof window.process !== 'undefined',
    titulo: document.title,
    desborde: document.documentElement.scrollWidth > window.innerWidth + 1,
  }))()`);

  log(`destinos=${visto.destinos} iconos=${visto.iconos} titulo="${visto.titulo}"`);

  if (visto.destinos !== DESTINOS) {
    fallas.push(`la barra lateral tiene ${visto.destinos} destinos, esperaba ${DESTINOS}`);
  }
  if (visto.iconos < DESTINOS) {
    fallas.push(`sólo ${visto.iconos} iconos SVG dibujados, esperaba al menos ${DESTINOS}`);
  }
  if (visto.colapsados) {
    fallas.push(`${visto.colapsados} icono(s) con 0 px de lado`);
  }
  if (!visto.puente) {
    fallas.push("el preload no expuso window.mvClienteIA (contextBridge roto)");
  }
  // Esto no es cosmético: con nodeIntegration colado, cualquier script que
  // entre a la ventana tendría el sistema de archivos del usuario.
  if (visto.nodeExpuesto) {
    fallas.push("¡Node quedó expuesto al render! contextIsolation/nodeIntegration mal");
  }
  if (visto.desborde) {
    fallas.push("la ventana desborda horizontalmente");
  }
  if (errores.length) {
    fallas.push(`errores de consola: ${errores.slice(0, 3).join(" | ")}`);
  }

  if (rutaCaptura) {
    const img = await ventana.webContents.capturePage();
    fs.writeFileSync(rutaCaptura, img.toPNG());
    log(`captura en ${rutaCaptura}`);
  }
}

app.disableHardwareAcceleration();
app.whenReady()
  .then(correr)
  .catch((e) => fallas.push(`excepción: ${e.message}`))
  .finally(() => {
    if (motor && !motor.killed) motor.kill();
    if (fallas.length) {
      process.stdout.write("\nHUMO ELECTRON: FALLA\n");
      for (const f of fallas) process.stdout.write(`  - ${f}\n`);
      app.exit(1);
    } else {
      process.stdout.write("\nHUMO ELECTRON: OK\n");
      app.exit(0);
    }
  });

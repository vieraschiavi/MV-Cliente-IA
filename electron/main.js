/*
 * MV Cliente IA · app de escritorio (Electron)
 * =============================================
 * Proceso principal: levanta el backend (FastAPI + el build de React) en un
 * puerto libre de 127.0.0.1 y abre la ventana apuntando ahí. Es la MISMA
 * interfaz que corre en la nube, como programa de PC.
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

if (process.env.MVCLIENTE_GPU !== "1") {
  app.disableHardwareAcceleration();
  app.commandLine.appendSwitch("disable-gpu-compositing");
}

const ESPERA_BACKEND_MS = 90_000;   // el primer arranque instalado carga el catálogo
let ventana = null;
let backend = null;
let cerrando = false;

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
  };
}

async function arrancar() {
  const puerto = await puertoLibre();
  const { cmd, args, cwd } = comandoBackend(puerto);

  backend = spawn(cmd, args, {
    cwd,
    // El backend escucha SÓLO en 127.0.0.1, así que no hace falta contraseña
    // para hablar con tu propia máquina (ver el docstring de webapp/backend).
    env: { ...process.env, MVCLIENTE_PUERTO: String(puerto), PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  backend.stdout.on("data", (d) => process.stdout.write(`[motor] ${d}`));
  backend.stderr.on("data", (d) => process.stderr.write(`[motor] ${d}`));
  backend.on("exit", (code) => {
    // Si el motor se muere solo, la ventana queda mostrando una página que ya
    // no responde: es peor que decirlo.
    if (!cerrando && code !== 0) {
      dialog.showErrorBox("MV Cliente IA",
        `El motor se detuvo (código ${code}). Cerrá la aplicación y volvé a abrirla.`);
    }
  });

  const url = `http://127.0.0.1:${puerto}/`;
  try {
    await esperarBackend(`${url}api/salud`, ESPERA_BACKEND_MS);
  } catch (e) {
    dialog.showErrorBox("MV Cliente IA", `No se pudo iniciar el motor: ${e.message}`);
    app.quit();
    return;
  }

  ventana = new BrowserWindow({
    width: 1400, height: 940, minWidth: 900, minHeight: 620,
    backgroundColor: "#0a1020",
    title: "MV Cliente IA",
    icon: path.join(__dirname, "build", process.platform === "win32" ? "icon.ico" : "icon.png"),
    webPreferences: { contextIsolation: true, nodeIntegration: false,
                      preload: path.join(__dirname, "preload.js") },
  });
  Menu.setApplicationMenu(null);
  // Los enlaces externos (un sitio de prospecto) van al navegador del sistema,
  // no reemplazan la ventana de la app.
  ventana.webContents.setWindowOpenHandler(({ url: destino }) => {
    shell.openExternal(destino);
    return { action: "deny" };
  });
  ventana.on("closed", () => { ventana = null; });
  await ventana.loadURL(url);
}

app.whenReady().then(arrancar);

app.on("window-all-closed", () => { app.quit(); });

app.on("before-quit", () => {
  cerrando = true;
  if (backend && !backend.killed) backend.kill();
});

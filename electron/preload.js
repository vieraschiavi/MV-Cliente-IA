// Sin puente hacia Node: la interfaz sólo habla con el backend por HTTP, así
// que no hace falta exponerle nada del sistema operativo. El preload existe
// para poder declarar contextIsolation:true sin advertencias y para dejar una
// marca de que corre dentro de la app de escritorio.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("mvClienteIA", {
  escritorio: true,
  version: process.versions.electron,
});

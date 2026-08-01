// Traducciones de la interfaz — los tres idiomas del producto (es/pt/en),
// los mismos que MV Kobra AI.
//
// A diferencia de Kobra, acá el idioma NO viene del país del tenant: lo elige
// el usuario y queda en localStorage. El motivo es el propio producto — quien
// lo usa está en Uruguay y le escribe a Brasil y a Estados Unidos, así que su
// idioma de trabajo no tiene por qué ser el del destinatario. El idioma de
// CADA CORREO sí sale del país del decisor, y eso lo decide el backend.
import en from "./en.json";
import es from "./es.json";
import ptBR from "./pt-BR.json";
import { getIdioma, setIdioma } from "../api.js";

export const IDIOMAS = [
  { codigo: "es", etiqueta: "ES" },
  { codigo: "pt", etiqueta: "PT" },
  { codigo: "en", etiqueta: "EN" },
];

const DICCIONARIOS = { es, pt: ptBR, en };

function buscar(dic, ruta) {
  return ruta.split(".").reduce((o, k) => (o == null ? o : o[k]), dic);
}

// t("explorar.titulo") · t("explorar.progreso", { hechas: 3, total: 6 })
export function t(clave, vars) {
  const idioma = getIdioma();
  let valor = buscar(DICCIONARIOS[idioma] || DICCIONARIOS.es, clave);
  if (valor == null) valor = buscar(DICCIONARIOS.es, clave); // falta la clave traducida
  if (valor == null) return clave;                            // último recurso
  if (vars) {
    for (const k of Object.keys(vars)) valor = valor.replaceAll(`{{${k}}}`, vars[k]);
  }
  return valor;
}

export function cambiarIdioma(codigo) {
  if (!DICCIONARIOS[codigo]) return;
  setIdioma(codigo);
  // Recargar es lo más simple y lo más seguro: `t()` se resuelve en el
  // render de cada componente y no hay contexto que propague el cambio.
  window.location.reload();
}

export { getIdioma };

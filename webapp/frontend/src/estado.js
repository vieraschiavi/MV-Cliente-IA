// Estado compartido: cuál es la corrida abierta y cómo se sigue su avance.
//
// La corrida activa vive en localStorage para que las cinco pantallas hablen
// de la misma sin pasarse props ni montar un store: al volver de "Correos" a
// "Explorar" se sigue viendo lo mismo, y si se cierra la app y se vuelve a
// abrir, la última búsqueda sigue ahí.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const KEY = "mvcliente_corrida";
// Cada cuánto se le pregunta al backend por el avance mientras corre. 900 ms
// es suficiente para que el acordeón se vea "en vivo" sin castigar al server.
const INTERVALO_MS = 900;

export function getCorridaId() {
  return localStorage.getItem(KEY) || "";
}
export function setCorridaId(id) {
  if (id) localStorage.setItem(KEY, id);
  else localStorage.removeItem(KEY);
}

/**
 * Devuelve { corrida, cargando, error, refrescar }.
 * Mientras el estado sea "corriendo" vuelve a pedirla sola; cuando termina,
 * deja de sondear (no hay timers colgados detrás de una corrida terminada).
 */
export function useCorrida(id) {
  const [corrida, setCorrida] = useState(null);
  const [cargando, setCargando] = useState(Boolean(id));
  const [error, setError] = useState("");
  const timer = useRef(null);
  const vivo = useRef(true);

  const traer = useCallback(async () => {
    if (!id) {
      setCorrida(null);
      setCargando(false);
      return null;
    }
    try {
      const d = await api(`/api/corridas/${id}`);
      if (!vivo.current) return null;
      setCorrida(d);
      setError("");
      return d;
    } catch (e) {
      if (!vivo.current) return null;
      // Una corrida recién lanzada puede tardar un instante en existir en
      // disco: el 404 no se muestra como error, se reintenta.
      if (e.status !== 404) setError(e.message);
      return null;
    } finally {
      if (vivo.current) setCargando(false);
    }
  }, [id]);

  useEffect(() => {
    vivo.current = true;
    let cancelado = false;

    const ciclo = async () => {
      const d = await traer();
      if (cancelado || !vivo.current) return;
      const sigue = !d || d.estado === "corriendo" || d.estado === "pendiente";
      if (sigue) timer.current = setTimeout(ciclo, INTERVALO_MS);
    };
    ciclo();

    return () => {
      cancelado = true;
      vivo.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [traer]);

  return { corrida, cargando, error, refrescar: traer };
}

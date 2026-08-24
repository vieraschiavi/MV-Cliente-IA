import React, { useEffect, useState } from "react";
import { pagoLicencia, setLicenciaClave } from "../api.js";
import { Copiar } from "./Comunes.jsx";
import { Icono } from "./Iconos.jsx";
import { t } from "../i18n/index.js";

/**
 * Lee `?pago=…` de la URL de vuelta de MercadoPago. Va FUERA del hash (el
 * HashRouter no la toca), así que se lee con `window.location.search` y no
 * con `useLocation()`.
 *
 * Hasta acá el comprador pagaba, MercadoPago lo devolvía a `/?pago=ok` y ahí
 * terminaba todo: `POST /api/pago/licencia` existía en el backend pero nada
 * en el frontend lo llamaba. Esto cierra ese agujero: canjea el `payment_id`
 * por la clave, la deja activada en este dispositivo (`setLicenciaClave`) y
 * la muestra para que el comprador la guarde también en la PC o el celular.
 */
export default function PagoConfirmado() {
  const [estado, setEstado] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pago = params.get("pago");
    if (!pago) return;
    const paymentId = params.get("payment_id") || params.get("collection_id") || "";
    // Se limpia la URL enseguida: si el comprador recarga la página no se
    // vuelve a canjear el mismo id ni a repetir el cartel.
    window.history.replaceState(null, "", window.location.pathname + window.location.hash);

    if (pago === "pendiente") { setEstado({ tipo: "pendiente" }); return; }
    if (pago !== "ok" || !paymentId) { setEstado({ tipo: "error", msg: "" }); return; }

    setEstado({ tipo: "cargando" });
    pagoLicencia(paymentId)
      .then((r) => {
        setLicenciaClave(r.clave);
        setEstado({ tipo: "ok", clave: r.clave, vence: r.vence });
      })
      .catch((err) => setEstado({ tipo: "error", msg: err.message }));
  }, []);

  if (!estado) return null;

  return (
    <div className="pago-overlay">
      <div className="card pago-card">
        {estado.tipo === "cargando" && (
          <p>{t("pago.cargando")}</p>
        )}
        {estado.tipo === "pendiente" && (
          <>
            <h3><Icono nombre="reloj" tam={18} /> {t("pago.pendiente_titulo")}</h3>
            <p>{t("pago.pendiente_txt")}</p>
            <button className="btn" onClick={() => setEstado(null)}>{t("pago.cerrar")}</button>
          </>
        )}
        {estado.tipo === "error" && (
          <>
            <h3><Icono nombre="alerta" tam={18} /> {t("pago.error_titulo")}</h3>
            <p>{estado.msg || t("pago.error_txt")}</p>
            <button className="btn" onClick={() => setEstado(null)}>{t("pago.cerrar")}</button>
          </>
        )}
        {estado.tipo === "ok" && (
          <>
            <h3><Icono nombre="chequeo" tam={18} /> {t("pago.ok_titulo")}</h3>
            <p>{t("pago.ok_txt")}</p>
            <div className="pago-clave tnum">{estado.clave}</div>
            <Copiar texto={estado.clave} />
            {estado.vence ? <p className="nota">{t("pago.vence", { fecha: estado.vence })}</p> : null}
            <p className="nota">{t("pago.ok_nota")}</p>
            <button className="btn" onClick={() => setEstado(null)}>{t("pago.cerrar")}</button>
          </>
        )}
      </div>
    </div>
  );
}

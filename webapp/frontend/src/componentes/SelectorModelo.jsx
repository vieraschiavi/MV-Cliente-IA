import React, { useState } from "react";
import { CATALOGO_MODELOS, getModelosDisponibles, RE_MODELO } from "../api.js";
import { t } from "../i18n/index.js";

const OTRO = "__otro__";

/**
 * Selector de modelo de IA, el mismo en Configuración y en Explorar.
 *
 * Tres fuentes, en este orden: el catálogo verificado del proveedor (se puede
 * elegir sin clave — antes, con la clave rechazada, sólo había «el de
 * siempre»), la lista que trajo «Actualizar» con la clave del usuario, y
 * «Otro modelo», que deja escribir cualquier ID que el proveedor acepte.
 * Un modelo guardado que no esté en ninguna lista se muestra igual: si no,
 * el select caería al default sin avisar y la corrida usaría otro modelo.
 */
export default function SelectorModelo({ proveedor, valor, onChange, id = "modelo-ia",
                                         modelos: traidos }) {
  const catalogo = CATALOGO_MODELOS[proveedor] || [];
  const delCatalogo = new Set(catalogo.map((m) => m.id));
  const disponibles = (traidos || getModelosDisponibles(proveedor))
    .filter((m) => !delCatalogo.has(m));
  const conocido = !valor || delCatalogo.has(valor) || disponibles.includes(valor);
  const [escribiendo, setEscribiendo] = useState(!conocido);
  const [texto, setTexto] = useState(conocido ? "" : valor);
  const invalido = escribiendo && texto.trim() && !RE_MODELO.test(texto.trim());

  const elegir = (v) => {
    if (v === OTRO) {
      setEscribiendo(true);
      setTexto(valor && conocido ? "" : valor || "");
      return;
    }
    setEscribiendo(false);
    onChange(v);
  };

  return (
    <>
      <select id={id} value={escribiendo ? OTRO : valor} style={{ flex: "1 1 220px" }}
              onChange={(e) => elegir(e.target.value)}>
        <option value="">{t("config.modelo_default")}</option>
        {catalogo.length ? (
          <optgroup label={t("config.modelo_sugeridos")}>
            {catalogo.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre} · {t(`config.nivel_${m.nivel}`)}
              </option>
            ))}
          </optgroup>
        ) : null}
        {disponibles.length ? (
          <optgroup label={t("config.modelo_con_tu_clave")}>
            {disponibles.map((m) => <option key={m} value={m}>{m}</option>)}
          </optgroup>
        ) : null}
        <option value={OTRO}>{t("config.modelo_otro")}</option>
      </select>
      {escribiendo ? (
        <input type="text" value={texto} aria-label={t("config.modelo_otro")}
               placeholder={t("config.modelo_otro_ph")} style={{ flex: "1 1 220px" }}
               autoCapitalize="none" autoCorrect="off" spellCheck="false"
               aria-invalid={invalido ? "true" : "false"}
               onChange={(e) => {
                 const v = e.target.value;
                 setTexto(v);
                 // Sólo se guarda un ID con forma válida: uno roto lo
                 // rechazaría el servidor recién al buscar.
                 if (!v.trim() || RE_MODELO.test(v.trim())) onChange(v.trim());
               }} />
      ) : null}
      {invalido ? <p className="error-note" style={{ flexBasis: "100%" }}>
        {t("config.modelo_invalido")}</p> : null}
    </>
  );
}

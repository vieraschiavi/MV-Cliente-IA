import React, { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, getOwner, getToken, setToken } from "./api.js";
import { Icono } from "./componentes/Iconos.jsx";
import { IDIOMAS, cambiarIdioma, getIdioma, t } from "./i18n/index.js";

import Analisis from "./pages/Analisis.jsx";
import Correos from "./pages/Correos.jsx";
import Configuracion from "./pages/Configuracion.jsx";
import Decisores from "./pages/Decisores.jsx";
import Explorar from "./pages/Explorar.jsx";
import Historial from "./pages/Historial.jsx";
import Login from "./pages/Login.jsx";
import Metricas from "./pages/Metricas.jsx";
import Panel from "./pages/Panel.jsx";
import Prospectos from "./pages/Prospectos.jsx";

// `ico` es el nombre de un trazo de componentes/Iconos.jsx, no un emoji: el
// emoji lo dibujaba la fuente del sistema y la barra salía de otro color en
// cada plataforma (ver el encabezado de ese archivo).
const NAV = [
  { ruta: "/", ico: "brujula", clave: "nav.explorar" },
  { ruta: "/prospectos", ico: "diana", clave: "nav.prospectos" },
  { ruta: "/decisores", ico: "ficha", clave: "nav.decisores" },
  { ruta: "/correos", ico: "sobre", clave: "nav.correos" },
  { ruta: "/analisis", ico: "barras", clave: "nav.analisis" },
  { ruta: "/metricas", ico: "tendencia", clave: "nav.metricas" },
  { ruta: "/historial", ico: "reloj", clave: "nav.historial" },
  // Sólo para el dueño: mide el NEGOCIO (ventas, plata, descargas), no
  // las campañas del cliente. Sin código de dueño ni se ofrece el enlace,
  // y el backend contesta 403 igual.
  { ruta: "/panel", ico: "escudo", clave: "nav.panel", soloDueno: true },
  { ruta: "/configuracion", ico: "ajustes", clave: "nav.configuracion" },
];

export function Marca() {
  return (
    <div className="brand">
      <img src="./mv_icon.png" alt={t("common.marca_texto")} />
      <b dangerouslySetInnerHTML={{ __html: t("common.marca") }} />
    </div>
  );
}

/**
 * El nombre del producto cambia con el idioma —en inglés se llama
 * "MV SearchCostumer AI"— así que el título de la pestaña y el atributo `lang`
 * del documento no pueden quedar fijos en el index.html: se sincronizan con el
 * idioma elegido en cuanto arranca la app.
 */
function useTituloDelDocumento() {
  useEffect(() => {
    document.title = t("common.titulo_pagina");
    document.documentElement.lang = getIdioma() === "pt" ? "pt-BR" : getIdioma();
  }, []);
}

export function SelectorIdioma() {
  const actual = getIdioma();
  return (
    <div className="lang-chip">
      {IDIOMAS.map((i) => (
        <button
          key={i.codigo}
          className={i.codigo === actual ? "on" : ""}
          onClick={() => cambiarIdioma(i.codigo)}
          aria-pressed={i.codigo === actual}
        >
          {i.etiqueta}
        </button>
      ))}
    </div>
  );
}

function Sidebar() {
  const nav = useNavigate();
  const loc = useLocation();
  return (
    <aside className="sidebar">
      <Marca />
      {NAV.filter((n) => !n.soloDueno || getOwner()).map((n) => (
        <button
          key={n.ruta}
          onClick={() => nav(n.ruta)}
          className={"nav-item" + (loc.pathname === n.ruta ? " on" : "")}
        >
          <span className="ico"><Icono nombre={n.ico} tam={18} /></span>
          {/* Dos etiquetas: la larga en escritorio y una corta abajo en el
              celular, donde seis destinos comparten 360 px de ancho. Con la
              larga, "Configuración" se partía a la mitad. El CSS muestra una
              sola de las dos. */}
          <span className="txt">{t(n.clave)}</span>
          <span className="txt-corto">{t(n.clave.replace("nav.", "nav_corto."))}</span>
        </button>
      ))}
      <div className="spacer" />
      <SelectorIdioma />
    </aside>
  );
}

/** Encabezado que sólo se ve en móvil: la marca y el idioma que en escritorio
 *  viven en la barra lateral (que abajo pasa a ser barra de navegación). */
function TopMovil() {
  return (
    <div className="top-movil">
      <Marca />
      <SelectorIdioma />
    </div>
  );
}

export default function App() {
  // undefined = todavía no se sabe si la instancia pide contraseña. Se espera
  // para no pintar el login un instante en el modo local (PC/APK), donde no
  // hay contraseña ninguna.
  const [auth, setAuth] = useState(undefined);
  const loc = useLocation();
  useTituloDelDocumento();

  useEffect(() => {
    api("/api/auth/estado")
      .then((e) => setAuth(Boolean(e.auth)))
      // Sin backend alcanzable (APK recién instalado, sin servidor
      // configurado) se entra igual: Configuración es lo primero que hay
      // que poder abrir, y ahí se arregla.
      .catch(() => setAuth(false));
  }, []);

  if (auth === undefined) return null;
  if (auth && !getToken() && loc.pathname !== "/login") return <Navigate to="/login" replace />;
  if (loc.pathname === "/login") return <Login onEntrar={() => setAuth(true)} />;

  return (
    <div className="layout">
      <Sidebar />
      <main className="main">
        <TopMovil />
        <Routes>
          <Route path="/" element={<Explorar />} />
          <Route path="/prospectos" element={<Prospectos />} />
          <Route path="/decisores" element={<Decisores />} />
          <Route path="/correos" element={<Correos />} />
          <Route path="/analisis" element={<Analisis />} />
          <Route path="/metricas" element={<Metricas />} />
          <Route path="/historial" element={<Historial />} />
          <Route path="/panel" element={<Panel />} />
          <Route path="/configuracion" element={<Configuracion onSalir={() => setToken(null)} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

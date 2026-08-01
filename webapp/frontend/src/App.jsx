import React, { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, getToken, setToken } from "./api.js";
import { IDIOMAS, cambiarIdioma, getIdioma, t } from "./i18n/index.js";
import Correos from "./pages/Correos.jsx";
import Configuracion from "./pages/Configuracion.jsx";
import Decisores from "./pages/Decisores.jsx";
import Explorar from "./pages/Explorar.jsx";
import Historial from "./pages/Historial.jsx";
import Login from "./pages/Login.jsx";
import Prospectos from "./pages/Prospectos.jsx";

const NAV = [
  { ruta: "/", ico: "🚀", clave: "nav.explorar" },
  { ruta: "/prospectos", ico: "🎯", clave: "nav.prospectos" },
  { ruta: "/decisores", ico: "📇", clave: "nav.decisores" },
  { ruta: "/correos", ico: "✉️", clave: "nav.correos" },
  { ruta: "/historial", ico: "🕘", clave: "nav.historial" },
  { ruta: "/configuracion", ico: "⚙️", clave: "nav.configuracion" },
];

export function Marca() {
  return (
    <div className="brand">
      <img src="./mv_icon.png" alt="MV Cliente IA" />
      <b dangerouslySetInnerHTML={{ __html: t("common.marca") }} />
    </div>
  );
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
      {NAV.map((n) => (
        <button
          key={n.ruta}
          onClick={() => nav(n.ruta)}
          className={"nav-item" + (loc.pathname === n.ruta ? " on" : "")}
        >
          <span className="ico">{n.ico}</span>
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
          <Route path="/historial" element={<Historial />} />
          <Route path="/configuracion" element={<Configuracion onSalir={() => setToken(null)} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

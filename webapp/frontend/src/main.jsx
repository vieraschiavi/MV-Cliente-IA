import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App.jsx";
import "./theme.css";

// HashRouter y no BrowserRouter: la misma build tiene que funcionar servida
// por el backend, abierta desde el file:// del instalador de PC y dentro del
// WebView del APK, donde no hay un servidor que reescriba las rutas.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>
);

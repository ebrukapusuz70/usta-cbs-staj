/* React uygulamasını tarayıcıdaki root alanına bağlar.
 * App bileşenini ve ortak stil dosyalarını yükler. */
import React from "react";
import { createRoot } from "react-dom/client";
import "ol/ol.css";
import "./styles.css";
import App from "./App";

// createRoot, React bileşen ağacını index.html içindeki tek kök elemana bağlar.
createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ThemeProvider } from "./theme/theme";
import "./index.css";
import "./theme/tokens.css";
import "./primitives/primitives.css";
import "./shell/shell.css";
import "./features/workspace/workspace.css";
import "./features/shipment/shipments.css";
import "./features/landing/landing.css";
import "./features/dashboard/dashboard.css";
import "./features/settings/settings.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Application root element is missing.");
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
);

import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { SessionProvider } from "./lib/session";
import "./index.css";
import { API_URL } from "./lib/api";


// Wake the server early: free hosting sleeps when idle and starts slowly.
void fetch(`${API_URL}/api/health`).catch(() => undefined);

// StrictMode is left off on purpose: in development it mounts components twice,
// which would start every build twice.
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <SessionProvider>
      <App />
    </SessionProvider>
  </BrowserRouter>,
);
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { api } from "./lib/api";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Inbox from "./pages/Inbox";
import Alerts from "./pages/Alerts";
import Accounts from "./pages/Accounts";
import Security from "./pages/Security";
import Templates from "./pages/Templates";

function Protected({ children }) {
  const [state, setState] = React.useState("loading");
  React.useEffect(() => {
    api.me().then(() => setState("authenticated")).catch(() => setState("anonymous"));
  }, []);
  if (state === "loading") {
    return (
      <div className="app-background flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="flex flex-col items-center gap-4 text-sm text-slate-500">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
          Verificando sesión…
        </div>
      </div>
    );
  }
  return state === "authenticated" ? children : <Navigate to="/login" replace />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Protected><Layout /></Protected>}>
          <Route path="/" element={<Inbox />} />
          <Route path="/alertas" element={<Alerts />} />
          <Route path="/cuentas" element={<Accounts />} />
          <Route path="/plantillas" element={<Templates />} />
          <Route path="/seguridad" element={<Security />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);

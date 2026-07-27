import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { api } from "./lib/api";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Inbox from "./pages/Inbox";
import Alerts from "./pages/Alerts";
import Accounts from "./pages/Accounts";
import Security from "./pages/Security";
import Templates from "./pages/Templates";
import Subscriptions from "./pages/Subscriptions";

function Protected({ children }) {
  const [state, setState] = React.useState("loading");
  React.useEffect(() => { api.me().then(() => setState("authenticated")).catch(() => setState("anonymous")); }, []);
  if (state === "loading") return <div className="session-loader">Verificando sesión…</div>;
  return state === "authenticated" ? children : <Navigate to="/login" replace />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Protected><Layout /></Protected>}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/bandeja" element={<Inbox />} />
          <Route path="/alertas" element={<Alerts />} />
          <Route path="/suscripciones" element={<Subscriptions />} />
          <Route path="/cuentas" element={<Accounts />} />
          <Route path="/plantillas" element={<Templates />} />
          <Route path="/seguridad" element={<Security />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);

import { useEffect, useMemo, useState } from "react";
import { Activity as ActivityIcon, CheckCircle2, Clock3, RefreshCw, TriangleAlert } from "lucide-react";
import { api } from "../lib/api";
import { InlineLoading, Notice } from "../components/ui";

export default function ActivityPage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = async () => {
    setLoading(true); setError("");
    try { setEvents(await api.syncHistory(200)); }
    catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  const summary = useMemo(() => ({
    total: events.length,
    ok: events.filter((event) => event.status === "ok").length,
    errors: events.filter((event) => event.status === "error").length,
    newMessages: events.reduce((sum, event) => sum + event.new_messages, 0),
  }), [events]);
  return <div className="activity-page">
    <header className="activity-heading">
      <div><span>SUPERVISIÓN</span><h1>Actividad de sincronización</h1><p>Historial persistente de las últimas ejecuciones por cuenta.</p></div>
      <button type="button" className="btn-secondary" onClick={load} disabled={loading}><RefreshCw size={14} /> Actualizar</button>
    </header>
    {error && <Notice tone="error">{error}</Notice>}
    <section className="activity-summary" aria-label="Resumen del historial">
      <Summary icon={ActivityIcon} label="Ejecuciones" value={summary.total} />
      <Summary icon={CheckCircle2} label="Correctas" value={summary.ok} tone="success" />
      <Summary icon={TriangleAlert} label="Con error" value={summary.errors} tone="danger" />
      <Summary icon={Clock3} label="Mensajes nuevos" value={summary.newMessages} />
    </section>
    <section className="activity-card">
      {loading ? <InlineLoading label="Cargando actividad" /> : events.length === 0
        ? <div className="activity-empty"><ActivityIcon size={20} /><strong>Aún no hay ejecuciones registradas</strong><p>El historial aparecerá después de la próxima sincronización.</p></div>
        : <div className="activity-table-wrap"><table className="activity-table">
          <thead><tr><th>Estado</th><th>Cuenta</th><th>Resultado</th><th>Duración</th><th>Fecha</th></tr></thead>
          <tbody>{events.map((event) => <tr key={event.id}>
            <td><span className={`activity-status is-${event.status}`}>{event.status === "ok" ? <CheckCircle2 size={13} /> : <TriangleAlert size={13} />}{event.status === "ok" ? "Correcta" : "Error"}</span></td>
            <td><strong>{event.account_email}</strong></td>
            <td>{event.status === "ok" ? `${event.new_messages} nuevos de ${event.messages_found} encontrados` : <span title={event.error}>{event.error || "Error sin detalle"}</span>}</td>
            <td>{formatDuration(event.duration_ms)}</td>
            <td><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString("es-PE")}</time></td>
          </tr>)}</tbody>
        </table></div>}
    </section>
  </div>;
}

function Summary({ icon: Icon, label, value, tone = "" }) {
  return <div className={`activity-summary-item ${tone ? `is-${tone}` : ""}`}><Icon size={16} /><div><span>{label}</span><strong>{value}</strong></div></div>;
}

function formatDuration(milliseconds) {
  if (milliseconds < 1000) return `${milliseconds} ms`;
  return `${(milliseconds / 1000).toFixed(1)} s`;
}

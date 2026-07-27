import { AlertCircle, CheckCircle2, Inbox, LoaderCircle } from "lucide-react";

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="page-header">
      <div className="min-w-0 flex-1">
        {eyebrow && <span className="page-eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children }) {
  const Icon = tone === "success" ? CheckCircle2 : AlertCircle;
  return <div role={tone === "error" ? "alert" : "status"} className={`mc-notice is-${tone}`}><Icon className="mt-0.5 shrink-0" size={18} /><div>{children}</div></div>;
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }) {
  return (
    <div className="mc-empty-state">
      <span className="mc-empty-icon"><Icon size={22} /></span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function LoadingBlock({ rows = 4 }) {
  return <div aria-label="Cargando" className="space-y-4 p-5">{Array.from({ length: rows }, (_, index) => <div key={index} className="flex gap-3"><div className="skeleton h-9 w-9 shrink-0" /><div className="flex-1 space-y-2"><div className="skeleton h-3 w-1/3" /><div className="skeleton h-3 w-4/5" /></div></div>)}</div>;
}

export function InlineLoading({ label = "Cargando" }) {
  return <span className="inline-flex items-center gap-2"><LoaderCircle className="animate-spin" size={16} />{label}</span>;
}

export function StatusBadge({ status, children }) {
  const tone = ["ok", "active"].includes(status) ? "success" : ["error", "critical"].includes(status) ? "danger" : status === "warning" ? "warning" : "neutral";
  return <span className={`mc-status is-${tone}`}>{children}</span>;
}

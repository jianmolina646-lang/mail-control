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
  const styles = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200",
    error: "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200",
    warning: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200",
    info: "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200",
  };
  const Icon = tone === "success" ? CheckCircle2 : AlertCircle;
  return <div role={tone === "error" ? "alert" : "status"} className={`flex gap-2.5 rounded-md border p-3 text-sm ${styles[tone]}`}><Icon className="mt-0.5 shrink-0" size={17} /><div>{children}</div></div>;
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center px-6 py-10 text-center">
      <Icon size={24} className="mb-4 text-slate-400" />
      <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h3>
      <p className="mt-1 max-w-sm text-sm leading-6 text-slate-500">{description}</p>
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
  const styles = {
    ok: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300",
    active: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300",
    warning: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-300",
    error: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-300",
    critical: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-300",
    neutral: "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300",
  };
  return <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${styles[status] || styles.neutral}`}>{children}</span>;
}

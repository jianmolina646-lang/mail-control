import { Copy, KeyRound, Plus, Radio, TicketCheck } from "lucide-react";

const templates = [
  { icon: KeyRound, title: "Entrega de licencia", description: "Licencia, clave de activación e instrucciones de instalación.", color: "text-violet-600 bg-violet-100 dark:bg-violet-500/15" },
  { icon: Radio, title: "Acceso de streaming", description: "Credenciales, perfil asignado y fecha de renovación.", color: "text-sky-600 bg-sky-100 dark:bg-sky-500/15" },
  { icon: TicketCheck, title: "Ticket de soporte", description: "Respuesta rápida con número de caso y próximos pasos.", color: "text-emerald-600 bg-emerald-100 dark:bg-emerald-500/15" },
];

export default function Templates() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-semibold text-brand-600">Productividad</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-950 dark:text-white">Plantillas de ventas</h1>
          <p className="mt-1 text-sm text-slate-500">Respuestas consistentes para atender en segundos.</p>
        </div>
        <button className="btn-primary"><Plus size={17} /> Nueva plantilla</button>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {templates.map(({ icon: Icon, title, description, color }) => (
          <article key={title} className="card group p-5 transition hover:-translate-y-1 hover:border-brand-200">
            <div className={`mb-5 flex h-11 w-11 items-center justify-center rounded-xl ${color}`}><Icon size={21} /></div>
            <h2 className="font-semibold text-slate-900 dark:text-white">{title}</h2>
            <p className="mt-2 min-h-10 text-sm leading-5 text-slate-500">{description}</p>
            <button className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-brand-600 hover:text-brand-700"><Copy size={15} /> Usar plantilla</button>
          </article>
        ))}
      </div>
    </div>
  );
}

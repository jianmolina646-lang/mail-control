import { FileText } from "lucide-react";
import { EmptyState, PageHeader } from "../components/ui";

export default function Templates() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-7">
      <PageHeader eyebrow="Productividad" title="Plantillas de ventas" description="Contenido reutilizable para responder de forma consistente." />
      <section className="panel">
        <EmptyState
          icon={FileText}
          title="Las plantillas todavía no están disponibles"
          description="Esta sección está preparada para una futura implementación. No se muestran plantillas de ejemplo porque el backend aún no permite crearlas, editarlas ni enviarlas."
        />
      </section>
    </div>
  );
}

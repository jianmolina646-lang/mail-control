import { parseQuery } from "@/lib/mail-search";

export function replaceSearchOperator(query: string, key: string, value: string) {
  const rest = query.replace(new RegExp(`\\b${key}:("[^"]*"|[^\\s]+)`, "gi"), "").trim();
  const safe = value.replace(/["\r\n]/g, "").trim();
  return [rest, safe ? `${key}:"${safe}"` : ""].filter(Boolean).join(" ");
}

export function SearchFields({ query, onChange }: { query: string; onChange: (query: string) => void }) {
  const { ops } = parseQuery(query);
  const set = (key: string, value: string) => onChange(replaceSearchOperator(query, key, value));
  return <fieldset className="mail-search-fields">
    <legend>Búsqueda avanzada</legend>
    <label>Remitente<input type="text" value={ops.de ?? ""} placeholder="nombre@ejemplo.com" onChange={e => set("de", e.target.value)} /></label>
    <label>Desde<input type="date" value={ops.desde ?? ""} max={ops.hasta || undefined} onChange={e => set("desde", e.target.value)} /></label>
    <label>Hasta<input type="date" value={ops.hasta ?? ""} min={ops.desde || undefined} onChange={e => set("hasta", e.target.value)} /></label>
    <label>Lectura<select value={ops.estado ?? ""} onChange={e => set("estado", e.target.value)}><option value="">Todos</option><option value="no-leido">No leídos</option><option value="leido">Leídos</option></select></label>
    <label className="mail-search-check"><input type="checkbox" checked={!!ops.tiene} onChange={e => set("tiene", e.target.checked ? "adjuntos" : "")} /> Solo con adjuntos</label>
    <p>Se aplica a la cuenta y bandeja seleccionadas.</p>
  </fieldset>;
}

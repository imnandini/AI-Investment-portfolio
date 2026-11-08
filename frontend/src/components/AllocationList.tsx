import type { MixEntry } from "../services/api";

const palette = ["#128d83", "#477fa6", "#c28b40", "#8c76b3", "#6aa997", "#315a73"];

export function AllocationList({ title, entries, currency }: { title: string; entries: MixEntry[]; currency: string }) {
  return <section className="allocation-card">
    <div className="allocation-heading"><div><span className="section-kicker">COST BASIS MIX</span><h3>{title}</h3></div></div>
    {entries.length === 0 ? <p className="allocation-empty">Allocation appears after holdings are added in the portfolio base currency.</p> : <>
      <div className="allocation-stack" aria-label={`${title} allocation`}>
        {entries.map((entry, index) => <span key={entry.name} style={{ width: `${Math.max(Number(entry.allocation_pct ?? 0), 1)}%`, background: palette[index % palette.length] }} title={`${entry.name}: ${entry.allocation_pct ?? "—"}%`} />)}
      </div>
      <ul className="allocation-list">{entries.map((entry, index) => <li key={entry.name}>
        <span className="allocation-label"><i style={{ background: palette[index % palette.length] }} />{entry.name}</span>
        <span>{entry.allocation_pct === null ? "—" : `${Number(entry.allocation_pct).toFixed(1)}%`}</span>
        <small>{formatMoney(entry.cost_basis, currency)}</small>
      </li>)}</ul>
    </>}
  </section>;
}

export function formatMoney(value: string | null, currency: string) {
  if (value === null) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  try { return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(numeric); }
  catch { return `${numeric.toLocaleString("en-IN", { maximumFractionDigits: 2 })} ${currency}`; }
}

export function formatQuantity(value: string) {
  const number = Number(value);
  return Number.isFinite(number) ? new Intl.NumberFormat("en-IN", { maximumFractionDigits: 6 }).format(number) : value;
}

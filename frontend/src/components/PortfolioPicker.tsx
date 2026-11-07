import { useEffect, useState } from "react";
import { apiGet, type Portfolio } from "../services/api";

export function PortfolioPicker({ value, onChange, disabled = false }: { value: string; onChange: (id: string) => void; disabled?: boolean }) {
  const [items, setItems] = useState<Portfolio[]>([]);
  const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    apiGet<Portfolio[]>("/portfolios", controller.signal).then((rows) => { setItems(rows); if (rows[0]) onChange(rows[0].id); })
      .catch((cause: unknown) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load portfolios."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [onChange]);
  return <div className="research-toolbar"><label htmlFor="workspace-portfolio">Portfolio</label><select id="workspace-portfolio" value={value} disabled={disabled || loading} onChange={e => onChange(e.target.value)}><option value="">{loading ? "Loading…" : "Select a portfolio"}</option>{items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{error && <p role="alert">{error}</p>}{!loading && !items.length && !error && <p><a className="text-link" href="/portfolios">Create a portfolio to continue</a></p>}</div>;
}

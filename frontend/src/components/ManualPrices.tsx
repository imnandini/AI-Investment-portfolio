import { useState, type FormEvent } from "react";
import { apiPut, type Holding } from "../services/api";

export function ManualPrices({ portfolioId, holdings, onSaved }: { portfolioId: string; holdings: Holding[]; onSaved: () => Promise<void> }) {
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState("");
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    const holding = holdings.find(row => row.id === data.get("holding")); if (!holding) return;
    setBusy(true); setMessage("");
    try { await apiPut(`/portfolios/${portfolioId}/prices`, { symbol: holding.instrument.canonical_symbol, exchange: holding.instrument.exchange, currency: holding.instrument.currency, price: data.get("price"), as_of: new Date(String(data.get("as_of"))).toISOString() }); await onSaved(); setMessage("Manual reference price saved. Freshness is checked by the backend."); form.reset(); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "Could not save price."); } finally { setBusy(false); }
  }
  if (!holdings.length) return null;
  return <section className="surface-card research-card research-page"><h2>Manual reference prices</h2><p>Enter your own observed price and local as-of time. Saved prices are private to this portfolio. Prices older than seven days are marked stale.</p><form className="research-toolbar" onSubmit={save}><label>Holding<select name="holding" required>{holdings.map(row => <option key={row.id} value={row.id}>{row.instrument.canonical_symbol} · {row.instrument.exchange} · {row.instrument.currency}</option>)}</select></label><label>Price<input name="price" type="number" min="0.0000000001" step="any" required /></label><label>As of (local time)<input name="as_of" type="datetime-local" required /></label><button className="button button-primary" disabled={busy}>{busy ? "Saving…" : "Save price"}</button></form>{message && <p role="status">{message}</p>}</section>;
}

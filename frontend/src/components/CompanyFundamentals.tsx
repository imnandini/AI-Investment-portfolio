import { useState, type FormEvent } from "react";
import { apiGet } from "../services/api";
import { formatCompanyNumber, screenerTicker, type CompanyMatch, type CompanySearch, type CompanySnapshot } from "../services/companyResearch";

export function CompanyFundamentals({ name = "", symbol = "", exchange = "" }: { name?: string; symbol?: string; exchange?: string }) {
  const [query, setQuery] = useState(name || symbol);
  const [matches, setMatches] = useState<CompanyMatch[]>([]);
  const [snapshot, setSnapshot] = useState<CompanySnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  async function load(company: { symbol: string; exchange: string }) {
    setBusy(true); setError(""); setSnapshot(null); setNote("");
    try {
      setSnapshot(await apiGet<CompanySnapshot>(`/companies/${encodeURIComponent(company.symbol)}/snapshot?exchange=${encodeURIComponent(company.exchange)}`));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load company details."); }
    finally { setBusy(false); }
  }

  async function search(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNote(""); setSnapshot(null); setMatches([]);
    try {
      const ticker = screenerTicker(query.trim());
      if (ticker) { await load(ticker); return; }
      const result = await apiGet<CompanySearch>(`/companies/search?q=${encodeURIComponent(query.trim())}`);
      setMatches(result.matches); setNote(result.note);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Company search failed."); }
    finally { setBusy(false); }
  }

  return <section className="surface-card research-card" aria-labelledby="company-lookup-title">
    <h2 id="company-lookup-title">Company lookup</h2>
    <p>Search Indian companies by name or ticker, or paste a Screener company link. View financial details without uploading an annual report.</p>
    <form className="research-toolbar company-name-search" onSubmit={search}>
      <label>Company name, ticker or Screener URL<input required minLength={2} maxLength={300} value={query} onChange={event => setQuery(event.target.value)} placeholder="Aarti Industries, AARTIIND or a Screener link" disabled={busy} /></label>
      <button className="button button-primary" disabled={busy}>Search companies</button>
      {symbol && ["NSE", "BSE"].includes(exchange) && <button type="button" className="button button-secondary" disabled={busy} onClick={() => load({ symbol, exchange })}>Show holding details</button>}
    </form>
    {busy && <p role="status">Checking company data…</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {note && <p role="status">{note}</p>}
    {matches.length > 0 && <ul className="company-matches" aria-label="Matching companies">{matches.map(match => <li key={`${match.symbol}:${match.exchange}`}>
      <div><b>{match.name}</b><small>{match.symbol} · {match.exchange}</small></div>
      <button className="button button-secondary" disabled={busy} onClick={() => load(match)} aria-label={`View ${match.name} on ${match.exchange}`}>View details</button>
    </li>)}</ul>}
    {snapshot && <div className="company-result">
      <h3>{snapshot.name || snapshot.symbol} · {snapshot.exchange}</h3>
      <div className="company-source-links">
        <a className="text-link" href={snapshot.source_url} target="_blank" rel="noopener noreferrer">View Yahoo Finance source</a>
        <a className="text-link" href={snapshot.screener_url} target="_blank" rel="noopener noreferrer">Compare on Screener</a>
      </div>
      <p className="company-source-meta">{snapshot.provider} · Fetched {new Date(snapshot.retrieved_at).toLocaleString()}{snapshot.cached ? " · Saved snapshot" : ""}. Snapshots are cached for up to six hours.</p>
      {snapshot.status === "available" && <>
        <p>{snapshot.sector || "Sector unavailable"} · {snapshot.industry || "Industry unavailable"}</p>
        <p>Reference price: <b>{formatCompanyNumber(snapshot.price, "INR / share")}</b> · Price date: {snapshot.price_as_of ? new Date(snapshot.price_as_of).toLocaleString() : "Not supplied"}. Prices may be delayed.</p>
        <dl className="company-metrics">{snapshot.metrics.map(metric => <div key={metric.label}>
          <dt>{metric.label}</dt><dd>{formatCompanyNumber(metric.value, metric.unit)}</dd><small>{metric.period}</small>
        </div>)}</dl>
        {snapshot.statements.map(table => <details className="company-statement" key={table.title} open={table.title === "Annual profit & loss"}>
          <summary>{table.title}</summary><p>Amounts in {table.currency} crore; EPS in {table.currency} per share. Columns show period-end dates.</p>
          <div className="company-table-scroll" role="region" aria-label={table.title} tabIndex={0}><table>
            <thead><tr><th scope="col">Financial item</th>{table.periods.map(period => <th key={period} scope="col">{period}</th>)}</tr></thead>
            <tbody>{table.rows.map(row => <tr key={row.label}><th scope="row">{row.label}</th>{row.values.map((value, index) => <td key={index}>{formatCompanyNumber(value, row.unit === "per_share" ? "INR / share" : "INR")}</td>)}</tr>)}</tbody>
          </table></div>
        </details>)}
      </>}
      <ul>{snapshot.notes.map(item => <li key={item}>{item}</li>)}</ul>
    </div>}
    <p>Yahoo Finance supplies the in-app figures. Screener opens separately for comparison. Detailed risks, accounting policies and auditor notes still need company filings.</p>
  </section>;
}

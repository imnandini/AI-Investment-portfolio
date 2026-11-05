import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { AlertCircle, BriefcaseBusiness, Check, FileUp, LoaderCircle, Plus, RefreshCw, Upload, X } from "lucide-react";
import { AuthGate } from "../components/AuthGate";
import { AllocationList, formatMoney, formatQuantity } from "../components/AllocationList";
import { apiGet, apiPost, apiUpload, type Holding, type ImportResult, type Portfolio, type PortfolioAnalytics } from "../services/api";

function PortfolioWorkspace() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [analytics, setAnalytics] = useState<PortfolioAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [portfolioName, setPortfolioName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const refreshList = useCallback(async (preferredId?: string) => {
    const list = await apiGet<Portfolio[]>("/portfolios");
    setPortfolios(list);
    const nextId = (preferredId && list.some((item) => item.id === preferredId) ? preferredId : "") || (list.some((item) => item.id === selectedId) ? selectedId : list[0]?.id || "");
    setSelectedId(nextId);
    return nextId;
  }, [selectedId]);

  const refreshPositions = useCallback(async (portfolioId: string) => {
    const [nextHoldings, nextAnalytics] = await Promise.all([
      apiGet<Holding[]>(`/portfolios/${portfolioId}/holdings`),
      apiPost<PortfolioAnalytics>(`/portfolios/${portfolioId}/analytics`, { prices: [] }),
    ]);
    setHoldings(nextHoldings);
    setAnalytics(nextAnalytics);
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    apiGet<Portfolio[]>("/portfolios").then(async (list) => {
      if (!active) return;
      setPortfolios(list);
      const id = list[0]?.id ?? "";
      setSelectedId(id);
      if (id) {
        const [rows, summary] = await Promise.all([
          apiGet<Holding[]>(`/portfolios/${id}/holdings`),
          apiPost<PortfolioAnalytics>(`/portfolios/${id}/analytics`, { prices: [] }),
        ]);
        if (active) { setHoldings(rows); setAnalytics(summary); }
      } else if (active) { setHoldings([]); setAnalytics(null); }
    }).catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Could not load portfolios."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedId || loading) return;
    let active = true;
    setBusy(true);
    Promise.all([
      apiGet<Holding[]>(`/portfolios/${selectedId}/holdings`),
      apiPost<PortfolioAnalytics>(`/portfolios/${selectedId}/analytics`, { prices: [] }),
    ]).then(([rows, summary]) => { if (active) { setHoldings(rows); setAnalytics(summary); setError(null); } })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Could not load holdings."); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [selectedId, loading]);

  const selected = portfolios.find((portfolio) => portfolio.id === selectedId);
  const positionByKey = useMemo(() => new Map((analytics?.positions ?? []).map((position) => [`${position.symbol}:${position.exchange}`, position])), [analytics]);

  async function createPortfolio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const created = await apiPost<Portfolio>("/portfolios", { name: portfolioName.trim(), base_currency: "INR" });
      setPortfolioName(""); setShowCreate(false); setImportResult(null);
      const id = await refreshList(created.id);
      if (id) await refreshPositions(id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create portfolio."); }
    finally { setBusy(false); }
  }

  async function importCsv(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file || !selectedId) return;
    setBusy(true); setError(null); setImportResult(null); setImportMessage(null);
    try {
      const result = await apiUpload<ImportResult>(`/portfolios/${selectedId}/holdings/import`, file);
      setImportResult(result);
      setImportMessage(`${result.imported_count} holding${result.imported_count === 1 ? "" : "s"} imported.`);
      await refreshPositions(selectedId);
      await refreshList(selectedId);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not import the CSV file."); }
    finally { setBusy(false); }
  }

  async function reload() {
    if (!selectedId) return;
    setBusy(true); setError(null);
    try { await refreshPositions(selectedId); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not refresh portfolio."); }
    finally { setBusy(false); }
  }

  const csvTemplate = () => {
    const blob = new Blob(["symbol,exchange,asset_type,currency,sector,quantity,average_cost,purchase_date\n"], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "holdings_template.csv"; anchor.click(); URL.revokeObjectURL(url);
  };

  return <div className="subpage portfolio-page">
    <div className="eyebrow"><span className="eyebrow-line" /> PORTFOLIO WORKSPACE</div>
    <div className="subpage-heading"><div><h1>Your portfolios</h1><p>Holdings, cost basis, and price coverage from your own data.</p></div>
      <button className="button button-primary" type="button" onClick={() => setShowCreate((value) => !value)}><Plus size={16} />New portfolio</button>
    </div>

    {showCreate && <form className="create-portfolio surface-card" onSubmit={createPortfolio}><div><label htmlFor="portfolio-name">Portfolio name</label><input id="portfolio-name" maxLength={120} required value={portfolioName} onChange={(event) => setPortfolioName(event.target.value)} placeholder="e.g. Long-term investments" /></div><span className="base-currency-tag">Base currency · INR</span><button className="button button-primary" type="submit" disabled={busy}><Check size={15} />Create</button><button className="icon-button" type="button" aria-label="Close" onClick={() => setShowCreate(false)}><X size={16} /></button></form>}

    {error && <div className="alert-banner error-banner" role="alert"><AlertCircle size={16} /><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss"><X size={15} /></button></div>}
    {loading ? <div className="loading-card"><LoaderCircle className="spin" size={18} />Loading your portfolios…</div> : portfolios.length === 0 ? <section className="surface-card first-portfolio">
      <span className="auth-icon"><BriefcaseBusiness size={19} /></span><h2>Start with a portfolio</h2><p>Create a portfolio, then import a holdings CSV. We’ll calculate cost basis and show where prices are still missing.</p>
      <button className="button button-primary" type="button" onClick={() => setShowCreate(true)}><Plus size={15} />Create portfolio</button>
    </section> : <>
      <div className="portfolio-toolbar"><label htmlFor="portfolio-select">Portfolio</label><select id="portfolio-select" value={selectedId} onChange={(event) => { setImportResult(null); setImportMessage(null); setSelectedId(event.target.value); }}>
        {portfolios.map((portfolio) => <option key={portfolio.id} value={portfolio.id}>{portfolio.name}</option>)}
      </select><span className="currency-chip">{selected?.base_currency ?? "INR"} base</span><button className="icon-button refresh-button" type="button" onClick={reload} disabled={busy} aria-label="Refresh portfolio"><RefreshCw size={15} className={busy ? "spin" : ""} /></button>
        <label className={`button button-primary upload-button${busy ? " disabled" : ""}`}><Upload size={15} />Import CSV<input type="file" accept=".csv,text/csv" disabled={busy} onChange={importCsv} /></label>
        <button className="button button-secondary" type="button" onClick={csvTemplate}>Download template</button>
      </div>
      <div className="import-hint"><FileUp size={14} /><span>UTF-8 CSV · up to 500 rows · required columns: symbol, quantity, average_cost</span></div>

      {(importMessage || (importResult && importResult.errors.length > 0)) && <div className={`import-result${importResult?.errors.length ? " has-errors" : ""}`}>
        <div className="import-result-title">{importResult?.errors.length ? <AlertCircle size={16} /> : <Check size={16} />}<b>{importMessage}</b></div>
        {importResult?.errors.length ? <ul>{importResult.errors.map((item, index) => <li key={`${item.row}-${item.field}-${index}`}><b>Row {item.row}{item.field ? ` · ${item.field}` : ""}</b><span>{item.message}</span></li>)}</ul> : null}
      </div>}

      {analytics && <div className="portfolio-metrics">
        <article className="metric-card"><span>Cost basis</span><strong>{formatMoney(analytics.cost_basis_total, analytics.base_currency)}</strong><small>Backend calculated · {holdings.length} positions</small></article>
        <article className="metric-card"><span>Market value</span><strong>{formatMoney(analytics.market_value_total, analytics.base_currency)}</strong><small>{analytics.complete ? "Complete with fresh matching prices" : "Incomplete · price inputs needed"}</small></article>
        <article className="metric-card"><span>Unrealized P/L</span><strong>{formatMoney(analytics.unrealized_pl_total, analytics.base_currency)}</strong><small>Shown when market values are complete</small></article>
        <article className="metric-card"><span>Price coverage</span><strong>{analytics.priced_position_count} / {holdings.length}</strong><small>{analytics.unpriced_position_count} positions need a usable price</small></article>
      </div>}

      {analytics && analytics.completeness_notes.length > 0 && <div className="freshness-note"><AlertCircle size={15} /><div><b>Market metrics are partial</b><p>{analytics.completeness_notes.join(" ")}</p></div></div>}

      <div className="allocation-grid">
        <AllocationList title="By asset type" entries={analytics?.asset_mix ?? []} currency={selected?.base_currency ?? "INR"} />
        <AllocationList title="By sector" entries={analytics?.sector_mix ?? []} currency={selected?.base_currency ?? "INR"} />
      </div>

      <section className="surface-card positions-card"><div className="table-heading"><div><span className="section-kicker">POSITIONS</span><h2>Holdings</h2></div><span className="table-caption">Cost basis from quantity × average cost</span></div>
        {holdings.length === 0 ? <div className="holdings-empty"><BriefcaseBusiness size={20} /><b>No holdings in this portfolio</b><p>Import the CSV template to add positions. No sample figures are displayed.</p></div> : <div className="table-scroll"><table><thead><tr><th>Instrument</th><th>Quantity</th><th>Avg. cost</th><th>Cost basis</th><th>Current price</th><th>Market value</th><th>Allocation</th><th>Price freshness</th></tr></thead><tbody>
          {holdings.map((holding) => {
            const key = `${holding.instrument.canonical_symbol}:${holding.instrument.exchange}`;
            const position = positionByKey.get(key);
            const status = position?.price_status ?? "missing";
            return <tr key={holding.id}><td><b>{holding.instrument.canonical_symbol}</b><small>{holding.instrument.exchange} · {holding.instrument.asset_type}{holding.instrument.sector ? ` · ${holding.instrument.sector}` : ""}</small></td><td>{formatQuantity(holding.quantity)}</td><td>{formatMoney(holding.average_cost, holding.instrument.currency)}</td><td>{formatMoney(position?.cost_basis ?? null, holding.instrument.currency)}</td><td>{formatMoney(position?.current_price ?? null, holding.instrument.currency)}</td><td>{formatMoney(position?.market_value ?? null, holding.instrument.currency)}</td><td>{position?.market_allocation_pct !== null && position?.market_allocation_pct !== undefined ? `${Number(position.market_allocation_pct).toFixed(1)}%` : position?.cost_basis_allocation_pct != null ? `${Number(position.cost_basis_allocation_pct).toFixed(1)}% cost` : "—"}</td><td><span className={`freshness-pill freshness-${status}`}>{status.replaceAll("_", " ")}</span>{position?.price_as_of && <small>{new Date(position.price_as_of).toLocaleDateString()}</small>}</td></tr>;
          })}
        </tbody></table></div>}
      </section>
      <p className="portfolio-methodology">{analytics?.methodology}</p>
    </>}
  </div>;
}

export function PortfolioPage() {
  return <AuthGate><PortfolioWorkspace /></AuthGate>;
}

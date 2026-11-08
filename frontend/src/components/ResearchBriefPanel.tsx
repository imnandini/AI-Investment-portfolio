import { useEffect, useRef, useState } from "react";
import { LoaderCircle, RefreshCw, X } from "lucide-react";
import { getBrief, type NewsSignal, type ResearchBrief, type StockBrief } from "../services/briefs";
import { EvidencePanel } from "./EvidencePanel";

function Signals({ title, signals, brief, empty }: { title: string; signals: NewsSignal[]; brief: StockBrief; empty: string }) {
  return <section><h3>{title}</h3>{signals.length ? <ul className="brief-signals">{signals.map(signal => <li key={signal.title}><b>{signal.title}</b><p>{signal.text}</p><div>{signal.source_ids.map(id => {
    const source = brief.news.articles.find(article => article.id === id);
    return source && <a key={id} href={source.url} target="_blank" rel="noopener noreferrer">{source.title} ↗</a>;
  })}</div></li>)}</ul> : <p>{empty}</p>}</section>;
}

function StockContent({ brief }: { brief: StockBrief }) {
  const marketWeight = brief.portfolio_context.market_weight_pct;
  const costWeight = brief.portfolio_context.cost_weight_pct;
  return <>
    <p className="brief-view">{brief.view}</p>
    {(marketWeight !== null || costWeight !== null) && <p className="brief-meta">Your portfolio weight: {Number(marketWeight ?? costWeight).toFixed(1)}% of security {marketWeight !== null ? "market value" : "cost basis"}.</p>}
    <p className="brief-meta">Pros and cons below are potential signals from reported headlines. Confirm them against company disclosures.</p>
    <div className="brief-columns"><Signals title="Pros to investigate" signals={brief.pros} brief={brief} empty="No supported positive signals were identified in the recent matched headlines." /><Signals title="Cons to investigate" signals={brief.cons} brief={brief} empty="No specific concern signals were identified. This does not mean the stock is low risk." /></div>
    <section className="brief-news"><h3>Recent news · last 30 days</h3><p className="brief-meta">{brief.news.provider || "News feeds"} · Checked {new Date(brief.news.checked_at).toLocaleString()}{brief.news.cached ? " · Cached for up to 10 minutes" : ""}</p>
      {brief.news.articles.length ? <ul>{brief.news.articles.map(article => <li key={article.id}><a href={article.url} target="_blank" rel="noopener noreferrer">{article.title} ↗</a><small>{article.publisher} · {new Date(article.published_at).toLocaleString()}</small></li>)}</ul> : <p role="status">{brief.news.note}</p>}
    </section>
    {brief.evidence.length > 0 && <section><h3>From your uploaded sources</h3><EvidencePanel evidence={brief.evidence} /></section>}
    <details><summary>Questions and evidence limits</summary><ul>{[...brief.questions, ...brief.limitations].map((text, i) => <li key={i}>{text}</li>)}</ul></details>
  </>;
}

export function ResearchBriefPanel({ portfolioId, holdingId, name, onClose }: { portfolioId: string; holdingId?: string; name: string; onClose: () => void }) {
  const [brief, setBrief] = useState<ResearchBrief | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [revision, setRevision] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const request = useRef<{ key: string; promise: Promise<ResearchBrief> } | null>(null);
  useEffect(() => {
    let active = true;
    setBusy(true); setError(""); setBrief(null);
    const key = `${portfolioId}:${holdingId || "portfolio"}:${revision}`;
    // Share the request across React StrictMode's initial effect replay.
    if (request.current?.key !== key) request.current = { key, promise: getBrief(portfolioId, holdingId) };
    request.current.promise.then(value => { if (active) setBrief(value); })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "The research brief could not load."); })
      .finally(() => { if (active) setBusy(false); });
    heading.current?.focus({ preventScroll: true });
    heading.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    return () => { active = false; };
  }, [portfolioId, holdingId, revision]);
  return <section className="surface-card research-card research-page research-brief" aria-label="Research brief" aria-busy={busy}>
    <div className="brief-heading"><div><span className="section-kicker">{holdingId ? "STOCK BRIEF" : "PORTFOLIO OPINION"}</span><h2 ref={heading} tabIndex={-1}>{name}</h2></div><div className="brief-actions"><button className="button button-secondary" disabled={busy} onClick={() => setRevision(value => value + 1)}><RefreshCw size={14} />Refresh brief</button><button className="icon-button" aria-label="Close research brief" onClick={onClose}><X size={16} /></button></div></div>
    {busy && <p className="brief-loading" role="status"><LoaderCircle size={17} className="spin" />Checking recent company news and your saved portfolio…</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    {brief && <><p className="brief-meta">Prepared {new Date(brief.generated_at).toLocaleString()} · Research view · Not investment advice</p>
      {brief.kind === "stock" ? <StockContent brief={brief} /> : <>
        <p className="brief-view">{brief.view}</p><p className="brief-meta">{brief.security_count} securities · Weights use {brief.weight_basis} · {brief.pf_account_count} PF accounts shown separately</p>
        <div className="brief-columns"><section><h3>What looks constructive</h3>{brief.strengths.length ? <ul>{brief.strengths.map(text => <li key={text}>{text}</li>)}</ul> : <p>There is not enough evidence for a supported positive observation yet.</p>}</section><section><h3>What needs attention</h3><ul>{brief.concerns.map(text => <li key={text}>{text}</li>)}</ul></section></div>
        {brief.stocks.length > 0 && <section><h3>Company briefs and news</h3><p>Largest equity holdings by recorded cost basis, up to 10. Expand a company to see its pros, cons and news.</p>{brief.stocks.map(stock => <details className="brief-stock-detail" key={stock.holding_id}><summary>{stock.name}</summary><StockContent brief={stock} /></details>)}</section>}
        <details><summary>Questions and assessment limits</summary><ul>{[...brief.questions, ...brief.limitations].map((text, i) => <li key={i}>{text}</li>)}</ul></details>
      </>}
    </>}
  </section>;
}

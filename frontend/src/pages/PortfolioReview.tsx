import { useEffect, useState } from "react";
import { AuthGate } from "../components/AuthGate";
import { EvidencePanel } from "../components/EvidencePanel";
import { PortfolioPicker } from "../components/PortfolioPicker";
import { ReviewCompanyNews } from "../components/ReviewCompanyNews";
import { getReviews, launchReview, type Review } from "../services/reviews";
import { apiDelete } from "../services/api";

function statusLabel(status: string) {
  return status === "complete" ? "Review ready" : status === "partial" ? "Partial coverage" : status;
}

function ReviewWorkspace() {
  const [id, setId] = useState("");
  const [reviews, setReviews] = useState<Review[]>([]);
  const [selected, setSelected] = useState<Review | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setReviews([]); setSelected(null); setError("");
    if (!id) return;
    const controller = new AbortController();
    setLoading(true);
    getReviews(id, controller.signal).then(rows => { setReviews(rows); setSelected(rows[0] || null); })
      .catch((cause: unknown) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load reviews."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id]);
  async function launch() {
    setBusy(true); setError("");
    try { const review = await launchReview(id); setReviews(rows => [review, ...rows]); setSelected(review); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Review failed."); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!selected) return;
    setBusy(true); setError("");
    try { await apiDelete(`/portfolios/${id}/reviews/${selected.id}`); setReviews(rows => rows.filter(row => row.id !== selected.id)); setSelected(null); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not delete review."); }
    finally { setBusy(false); }
  }
  const report = selected?.report;
  const companies = report?.company_reviews || [];
  const sources = companies.flatMap(company => company.news.articles);
  const coverage = report?.coverage;
  return <div className="subpage research-page saved-review-page">
    <div className="eyebrow"><span className="eyebrow-line" /> PORTFOLIO REVIEW</div>
    <div className="subpage-heading"><div><h1>A clearer portfolio picture</h1><p>Your holdings, returns, concentration and recent company news, assessed and saved together. Documents are optional.</p></div></div>
    <PortfolioPicker value={id} onChange={setId} disabled={busy} />
    <div className="research-toolbar">
      <button className="button button-primary" onClick={launch} disabled={!id || busy || loading}>{busy ? "Reviewing…" : "Start review"}</button>
      {reviews.length > 0 && <label>Saved reviews<select value={selected?.id || ""} onChange={e => setSelected(reviews.find(row => row.id === e.target.value) || null)} disabled={busy}>
        <option value="">Choose a review</option>{reviews.map(row => <option key={row.id} value={row.id}>{new Date(row.created_at).toLocaleString()} · {statusLabel(row.status)}</option>)}
      </select></label>}
    </div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading saved reviews…</p>}
    {busy && <div role="status" className="research-notice">Checking daily prices, assessing every saved position and fetching recent news for the largest listed holdings…</div>}
    {!selected && !loading && <section className="surface-card research-card"><h2>No review selected</h2><p>Start a review for a portfolio-specific view of exposure, price returns and recent news. No company-document uploads are required. Large portfolios receive a clearly labeled news sample.</p></section>}
    {report && <article className="surface-card research-card">
      <div className="review-heading"><h2>{report.error ? "Review failed" : report.summary}</h2><span>{statusLabel(selected?.status || "")}</span></div>
      {report.error ? <p role="alert">{report.error}</p> : <>
        <p className="brief-meta">Saved {selected && new Date(selected.created_at).toLocaleString()} · Holdings, prices and news are a snapshot of this review.</p>
        {report.methodology_version !== "portfolio-review-v2" && <p className="research-notice">This saved review uses the older document-based format. Start a new review to include automatic company news and the updated portfolio assessment.</p>}
        {coverage && <section className="review-coverage" aria-label="Review coverage">
          <h3>What this review covers</h3>
          <p><b>{coverage.total_positions} positions calculated · {coverage.checked_positions} / {coverage.eligible_positions} listed holdings news-checked</b></p>
          <p>{coverage.positions_with_news} holdings with usable headlines · {coverage.article_count} distinct source links{coverage.checked_weight_pct !== null ? ` · Checked holdings represent ${coverage.checked_weight_pct}% of security ${coverage.weight_basis}` : ""}.</p>
          {coverage.unreviewed_positions > 0 && <p>{coverage.unreviewed_positions} listed holdings were not news-checked in this review. Their risks remain unassessed by the news sample.</p>}
          {coverage.excluded_positions > 0 && <p>{coverage.excluded_positions} other asset positions are outside the listed-stock/ETF news checks.</p>}
          <details><summary>How holdings were selected</summary><p>{coverage.selection_policy}</p></details>
        </section>}
        {report.findings.map((finding, index) => <section className="review-finding" key={index}>
          <small>{finding.basis === "headline_signal" ? "Headline topic with sources" : finding.basis.replaceAll("_", " ")}</small>
          <h3>{finding.title}</h3><p className="answer-text">{finding.text}</p>
          {finding.evidence_indices.length > 0 && <p>Document sources {finding.evidence_indices.map(item => `[${item + 1}]`).join(", ")}</p>}
          {finding.source_ids?.map(sourceId => {
            const source = sources.find(item => item.id === sourceId);
            return source && <a className="text-link review-source" key={sourceId} href={source.url} target="_blank" rel="noopener noreferrer">{source.title} · {source.publisher}</a>;
          })}
        </section>)}
        {companies.length > 0 && <section aria-label="Company and fund news"><h3>Company &amp; fund assessments</h3><p>Each assessment combines the holding's portfolio exposure with its dated news sources. An empty news feed does not establish that a company has no developments.</p>
          {companies.map((company, index) => <ReviewCompanyNews key={`${company.symbol}:${company.exchange}`} company={company} expanded={index === 0} />)}
        </section>}
        {report.evidence.length > 0 && <section><h3>Optional uploaded evidence</h3><EvidencePanel evidence={report.evidence} /></section>}
        <h3>Specific checks to follow up</h3><ul>{report.follow_up_questions.map(item => <li key={item}>{item}</li>)}</ul>
        <details className="review-limits"><summary>Data gaps &amp; assessment limits</summary><ul>{report.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>
        <details><summary>Methodology and activity</summary><small>{report.methodology_version}</small><p>{report.analytics.methodology}</p><ol>{report.activities.map(item => <li key={item}>{item}</li>)}</ol></details>
      </>}
      <button className="button button-secondary" onClick={remove} disabled={busy}>Delete saved review</button>
    </article>}
  </div>;
}
export function PortfolioReviewPage() { return <AuthGate><ReviewWorkspace /></AuthGate>; }

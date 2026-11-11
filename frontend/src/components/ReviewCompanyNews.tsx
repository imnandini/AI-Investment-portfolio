import type { CompanyReview } from "../services/reviews";
import type { NewsSignal } from "../services/briefs";
import { formatReturn } from "./HoldingReturn";

function SignalList({ title, signals, company }: { title: string; signals: NewsSignal[]; company: CompanyReview }) {
  if (!signals.length) return null;
  return <section><h4>{title}</h4><ul className="brief-signals">{signals.map(signal => <li key={signal.title}>
    <b>{signal.title}</b><p>{signal.explanation}</p><p><b>What to check:</b> {signal.text}</p>
    {signal.source_ids.map(id => {
      const article = company.news.articles.find(item => item.id === id);
      return article && <a className="text-link" key={id} href={article.url} target="_blank" rel="noopener noreferrer">{article.title}</a>;
    })}
  </li>)}</ul></section>;
}

export function ReviewCompanyNews({ company, expanded = false }: { company: CompanyReview; expanded?: boolean }) {
  return <details className="brief-stock-detail saved-review-company" open={expanded}>
    <summary>{company.name}{company.is_fund ? " · Fund/ETF" : ""}{company.weight_pct != null ? ` · ${company.weight_pct}% of ${company.weight_basis}` : ""}</summary>
    <p>{company.view}</p><p className="review-impact">{company.portfolio_impact}</p>
    {company.unrealized_return_pct != null && <p>Unrealized price return: <b>{formatReturn(company.unrealized_return_pct)}</b>{company.price_as_of ? ` · price date ${new Date(company.price_as_of).toLocaleDateString()}` : ""}</p>}
    <SignalList title="Positive topics in the headlines" signals={company.positive_signals} company={company} />
    <SignalList title="Concern topics in the headlines" signals={company.concern_signals} company={company} />
    <section className="brief-news"><h4>Recent news &amp; sources</h4>
      <p className="brief-meta">{company.news.checked_at ? `Checked ${new Date(company.news.checked_at).toLocaleString()}` : "Source check not completed"}{company.news.provider ? ` · ${company.news.provider}` : ""}{company.news.cached ? " · Cached feed" : ""}</p>
      <p>{company.news.note}</p>
      {company.news.articles.length > 0 && <ul>{company.news.articles.map(article => <li key={article.id}>
        <a className="text-link" href={article.url} target="_blank" rel="noopener noreferrer">{article.title}</a>
        <small>{article.publisher} · Published {new Date(article.published_at).toLocaleString()}</small>
      </li>)}</ul>}
    </section>
  </details>;
}

import { useEffect, useRef, useState, type FormEvent } from "react";
import { AuthGate } from "../components/AuthGate";
import { EvidencePanel } from "../components/EvidencePanel";
import { PortfolioPicker } from "../components/PortfolioPicker";
import { apiDelete, apiGet, apiPost } from "../services/api";
import type { Chat } from "../services/research";

const starters = [
  "Is my overall portfolio okay?",
  "What are my companies doing currently?",
  "How much is my portfolio worth?",
  "Is my portfolio diversified?",
];

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleString();
}

function ChatWorkspace() {
  const [id, setId] = useState("");
  const [messages, setMessages] = useState<Chat[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setMessages([]);
    setError("");
    setQuestion("");
    if (!id) return;
    const controller = new AbortController();
    setLoading(true);
    apiGet<Chat[]>(`/portfolios/${id}/chat`, controller.signal)
      .then(setMessages)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load chat.");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id]);

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!id || busy || loading || question.trim().length < 2) return;
    setBusy(true);
    setError("");
    try {
      const response = await apiPost<Chat>(`/portfolios/${id}/chat`, { question: question.trim() });
      setMessages(items => [...items, response]);
      setQuestion("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Chat failed.");
    } finally { setBusy(false); }
  }

  async function clear() {
    setBusy(true);
    setError("");
    try {
      await apiDelete(`/portfolios/${id}/chat`);
      setMessages([]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not clear history.");
    } finally { setBusy(false); }
  }

  return <div className="subpage research-page">
    <div className="eyebrow"><span className="eyebrow-line" /> PORTFOLIO CHAT</div>
    <div className="subpage-heading"><div>
      <h1>Ask about your portfolio</h1>
      <p>Explore your portfolio's health, allocation and recent company news. No document upload needed.</p>
    </div></div>
    <PortfolioPicker value={id} onChange={setId} disabled={busy} />
    {error && <p className="inline-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading chat history…</p>}
    <div className="chat-history" aria-busy={busy || loading}>
      {!loading && messages.length === 0 && <div className="surface-card research-card">
        <h2>Start with what you want to understand</h2>
        <p>Ask about your saved holdings or name a company you own to check its recent news. Uploaded reports are optional extra evidence.</p>
        <div className="chat-starters" aria-label="Suggested questions">{starters.map(starter =>
          <button type="button" className="button button-secondary" key={starter} disabled={!id || busy || loading}
            onClick={() => { setQuestion(starter); input.current?.focus(); }}>{starter}</button>
        )}</div>
      </div>}
      {messages.map(message => <article className="surface-card research-card" key={message.id}>
        <h3>{message.question}</h3>
        <div className="chat-context">{message.response.portfolio_context.name} · {message.response.portfolio_context.position_count} positions · recorded cost basis {message.response.portfolio_context.cost_basis ?? "unavailable"} {message.response.portfolio_context.currency}</div>
        <p className="brief-meta">Answered {formatDate(message.created_at)} · Saved portfolio snapshot</p>
        <p className="answer-text">{message.response.answer}</p>
        {!!message.response.news?.length && <section className="brief-news chat-news" aria-label="Company news sources">
          <h3>Recent company news &amp; sources</h3>
          {message.response.news.map(company => <div key={`${company.symbol}-${company.name}`}>
            <h4>{company.name}</h4>
            <p className="brief-meta">Checked {formatDate(company.checked_at)}{company.provider ? ` · ${company.provider}` : ""}{company.cached ? " · Cached news" : ""}</p>
            <p>{company.note}</p>
            {company.articles.length > 0 && <ul>{company.articles.map(article => <li key={article.id}>
              <a className="text-link" href={article.url} target="_blank" rel="noreferrer noopener">{article.title}</a>
              <small>{article.publisher} · Published {formatDate(article.published_at)}</small>
            </li>)}</ul>}
          </div>)}
        </section>}
        {message.response.evidence.length > 0 && <EvidencePanel evidence={message.response.evidence} />}
        <details><summary>How this answer was produced</summary><ol>{message.response.activities.map((activity, i) => <li key={i}>{activity}</li>)}</ol></details>
        {message.response.limitations.length > 0 && <details className="chat-limitations"><summary>Data gaps &amp; limitations</summary><ul>{message.response.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>}
      </article>)}
    </div>
    {busy && <p role="status">Checking saved portfolio metrics, recent company news and optional documents…</p>}
    <form className="surface-card research-card research-search" onSubmit={send}>
      <label htmlFor="chat-question">Your question<textarea ref={input} id="chat-question" value={question} onChange={e => setQuestion(e.target.value)}
        placeholder="Is my portfolio balanced? What is happening with a company I hold?"
        required minLength={2} maxLength={1000} disabled={!id || busy || loading} /></label>
      <p>Answers use saved holdings and available public news. Prices may be incomplete; news includes source dates. For company questions, include its name or symbol.</p>
      <div className="research-toolbar">
        <button className="button button-primary" disabled={!id || busy || loading || question.trim().length < 2}>Ask question</button>
        <button type="button" className="button button-secondary" disabled={!id || busy || loading || !messages.length} onClick={clear}>Clear history</button>
      </div>
    </form>
  </div>;
}

export function ResearchChatPage() { return <AuthGate><ChatWorkspace /></AuthGate>; }

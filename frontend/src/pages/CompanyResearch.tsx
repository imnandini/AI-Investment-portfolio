import { useEffect, useState, type FormEvent } from "react";
import { AuthGate } from "../components/AuthGate";
import { EvidencePanel } from "../components/EvidencePanel";
import { apiDelete, apiGet, apiPost, apiUpload } from "../services/api";
import type { Answer, DocumentRecord } from "../services/research";

type Company = { symbol: string; exchange: string; profile: { result: { data: { company_name: string; sector: string | null; currency: string | null } | null; issue: { message: string } | null }; retrieved_at: string }; price: { result: { data: { price: string; currency: string; as_of: string | null } | null; source: { provider: string } | null; issue: { message: string } | null } }; trend_note: string };

function ResearchWorkspace() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(true);
  const [symbol, setSymbol] = useState(""); const [exchange, setExchange] = useState("NSE");
  const [company, setCompany] = useState<Company | null>(null);
  const [question, setQuestion] = useState(""); const [answer, setAnswer] = useState<Answer | null>(null);
  const [companyFilter, setCompanyFilter] = useState(""); const [kindFilter, setKindFilter] = useState(""); const [periodFilter, setPeriodFilter] = useState("");
  useEffect(() => { const controller = new AbortController(); apiGet<DocumentRecord[]>("/documents", controller.signal).then(setDocuments).catch((cause: unknown) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load documents."); }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort(); }, []);
  async function lookup(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setCompany(null);
    try { setCompany(await apiGet<Company>(`/companies/${encodeURIComponent(symbol)}?exchange=${encodeURIComponent(exchange)}`)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Lookup failed."); } finally { setBusy(false); }
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); const file = data.get("file") as File;
    if (file.size > 5 * 1024 * 1024) { setError("PDF exceeds the 5 MB limit."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const doc = await apiUpload<DocumentRecord>("/documents", file, { title: data.get("title"), company: data.get("company"), kind: data.get("kind"), period: data.get("period") || null, publication_date: data.get("publication_date") || null, source_url: data.get("source_url") || null });
      setDocuments(rows => [doc, ...rows]); setNotice(doc.status === "ready" ? `Indexed ${doc.page_count} pages from ${doc.title}.` : doc.error || doc.status); form.reset();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Upload failed."); } finally { setBusy(false); }
  }
  async function remove(id: string) {
    if (!window.confirm("Delete this document? Saved chat and reviews containing your document excerpts will also be cleared.")) return;
    setBusy(true); setError("");
    try { await apiDelete(`/documents/${id}`); setDocuments(rows => rows.filter(row => row.id !== id)); setAnswer(null); setNotice("Document and saved research history deleted."); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Delete failed."); } finally { setBusy(false); }
  }
  async function ask(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setAnswer(null);
    try { setAnswer(await apiPost<Answer>("/documents/answer", { query: question, company: companyFilter || null, kind: kindFilter || null, period: periodFilter || null })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Search failed."); } finally { setBusy(false); }
  }
  return <div className="subpage research-page"><div className="eyebrow"><span className="eyebrow-line" /> COMPANY RESEARCH</div><div className="subpage-heading"><div><h1>Research with evidence</h1><p>Build your private document library and inspect cited passages.</p></div></div>
    {error && <p className="inline-error" role="alert">{error}</p>}{notice && <p className="research-notice" role="status">{notice}</p>}
    <section className="surface-card research-card"><h2>Company lookup</h2><form className="research-toolbar" onSubmit={lookup}><label>Symbol<input required maxLength={32} pattern="[A-Za-z0-9._-]+" value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} placeholder="e.g. INFY" /></label><label>Exchange<select value={exchange} onChange={e => setExchange(e.target.value)}><option>NSE</option><option>BSE</option></select></label><button className="button button-primary" disabled={busy}>Look up</button></form>
    {company && <div className="company-result"><h3>{company.profile.result.data?.company_name || `${company.symbol} · ${company.exchange}`}</h3><p>{company.profile.result.data ? `${company.profile.result.data.sector || "Sector unavailable"} · ${company.profile.result.data.currency || "Currency unavailable"}` : company.profile.result.issue?.message}</p><p>{company.price.result.data ? `${company.price.result.data.price} ${company.price.result.data.currency} · as of ${company.price.result.data.as_of || "unspecified"} · ${company.price.result.source?.provider}` : company.price.result.issue?.message}</p><small>Lookup checked {new Date(company.profile.retrieved_at).toLocaleString()} · {company.trend_note}</small></div>}</section>
    <section className="surface-card research-card"><h2>Add a research document</h2><p>Text PDFs up to 5 MB and 100 pages. Upload documents you are entitled to use. Originals are processed in memory; extracted text is stored privately.</p><form className="document-form" onSubmit={upload}><label>Title<input name="title" required maxLength={200} /></label><label>Company / ticker<input name="company" required maxLength={32} pattern="[A-Za-z0-9._-]+" /></label><label>Document kind<select name="kind"><option value="annual_report">Annual report</option><option value="quarterly_results">Quarterly results</option><option value="disclosure">Disclosure</option><option value="research">Research</option><option value="other">Other</option></select></label><label>Reporting period<input name="period" maxLength={40} placeholder="e.g. FY2026" /></label><label>Publication date<input name="publication_date" type="date" /></label><label>Original source URL<input name="source_url" type="url" maxLength={1000} placeholder="https://…" /></label><label>PDF file<input name="file" type="file" accept="application/pdf" required /></label><button className="button button-primary" disabled={busy}>{busy ? "Working…" : "Upload and index"}</button></form></section>
    <section className="surface-card research-card"><h2>Your document library</h2>{loading ? <p role="status">Loading documents…</p> : !documents.length ? <p>No documents yet. Upload a text PDF to begin.</p> : <ul className="document-list">{documents.map(doc => <li key={doc.id}><div><b>{doc.title}</b><small>{doc.company} · {doc.kind.replaceAll("_", " ")} · {doc.period || "No period"} · {doc.page_count} pages · {doc.status}</small>{doc.error && <p>{doc.error}</p>}</div><button className="button button-secondary" disabled={busy} onClick={() => remove(doc.id)}>Delete</button></li>)}</ul>}</section>
    <section className="surface-card research-card"><h2>Search your sources</h2><form onSubmit={ask} className="research-search"><label>Question<textarea required minLength={2} maxLength={1000} value={question} onChange={e => setQuestion(e.target.value)} placeholder="What does the report say about revenue and risk?" /></label><div className="research-toolbar"><label>Company filter<input maxLength={32} value={companyFilter} onChange={e => setCompanyFilter(e.target.value.toUpperCase())} placeholder="All companies" /></label><label>Kind<select value={kindFilter} onChange={e => setKindFilter(e.target.value)}><option value="">All kinds</option><option value="annual_report">Annual report</option><option value="quarterly_results">Quarterly results</option><option value="disclosure">Disclosure</option><option value="research">Research</option></select></label><label>Period<input maxLength={40} value={periodFilter} onChange={e => setPeriodFilter(e.target.value)} placeholder="All periods" /></label><button className="button button-primary" disabled={busy}>Find evidence</button></div></form>{answer && <div className="answer-result"><p className="answer-text">{answer.answer}</p><EvidencePanel evidence={answer.evidence} /><ul>{answer.limitations.map(item => <li key={item}>{item}</li>)}</ul></div>}</section>
  </div>;
}
export function CompanyResearchPage() { return <AuthGate><ResearchWorkspace /></AuthGate>; }

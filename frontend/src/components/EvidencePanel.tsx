import type { Evidence } from "../services/research";

export function EvidencePanel({ evidence }: { evidence: Evidence[] }) {
  return <section className="evidence-panel"><h3>Evidence and citations</h3>{evidence.length === 0 ? <p>No supporting passages found.</p> : evidence.map((item, i) => <details key={`${item.chunk_id}-${i}`} className="evidence-item"><summary>[{i + 1}] {item.title} · page {item.page}<small>{item.company} · {item.period || "Period unspecified"} · {item.publication_date || "Publication date unspecified"}</small></summary><blockquote>{item.text}</blockquote>{item.source_url && <a className="text-link" href={item.source_url} target="_blank" rel="noreferrer noopener">Open original source</a>}</details>)}</section>;
}

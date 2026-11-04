import { BookOpenText } from "lucide-react";
import { StatePanel } from "../components/StatePanel";

export function ResearchPage() {
  return <div className="subpage"><div className="eyebrow"><span className="eyebrow-line" /> COMPANY RESEARCH</div><div className="subpage-heading"><div><h1>Research with context</h1><p>Keep facts, dates, and source documents close to every question.</p></div></div><div className="surface-card empty-surface"><StatePanel icon={<BookOpenText size={19} />} title="Research library is empty" description="Company profiles and disclosure search will appear here once authorized data sources are connected. No external figures are shown without provenance." /></div></div>;
}

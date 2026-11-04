import { BriefcaseBusiness, Plus } from "lucide-react";
import { StatePanel } from "../components/StatePanel";

export function PortfolioPage() {
  return <div className="subpage"><div className="eyebrow"><span className="eyebrow-line" /> PORTFOLIO WORKSPACE</div><div className="subpage-heading"><div><h1>Your portfolios</h1><p>Organize holdings and review calculated metrics in one place.</p></div><button className="button button-primary" type="button" disabled title="Portfolio creation is part of the next frontend milestone"><Plus size={16} />New portfolio</button></div><div className="surface-card empty-surface"><StatePanel icon={<BriefcaseBusiness size={19} />} title="No portfolios yet" description="Create a portfolio or import your holdings to see your positions and analytics here. The portfolio editor is coming in the next milestone." /></div></div>;
}

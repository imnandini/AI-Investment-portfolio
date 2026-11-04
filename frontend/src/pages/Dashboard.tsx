import { ArrowRight, FileUp, Fingerprint, LineChart, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { ApiStatus } from "../components/ApiStatus";
import { StatePanel } from "../components/StatePanel";

const steps = [
  { n: "01", icon: FileUp, title: "Add your holdings", text: "Create a portfolio or import a CSV to get started.", to: "/portfolios", link: "Set up portfolio" },
  { n: "02", icon: LineChart, title: "Understand the numbers", text: "See cost basis, allocation, and risk with clear assumptions.", to: "/portfolios", link: "Explore analytics" },
  { n: "03", icon: Sparkles, title: "Research with evidence", text: "Bring company disclosures and sourced facts into view.", to: "/research", link: "Open research" },
];

export function DashboardPage() {
  return <div className="dashboard-page">
    <section className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line" /> YOUR RESEARCH WORKSPACE</div><h1>Good decisions start<br className="desktop-break" /> with a clearer picture.</h1><p className="welcome-copy">A calm place to understand your portfolio, follow the evidence, and see what is still unknown.</p></div><div className="welcome-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core"><Sparkles size={23} /></div><span className="orbit-point point-one" /><span className="orbit-point point-two" /></div></section>

    <section className="notice-card"><div className="notice-symbol"><ShieldCheck size={19} /></div><div className="notice-copy"><b>Your data, your context</b><p>Calculations use the holdings and prices you provide. Missing or stale inputs stay visible.</p></div><span className="notice-tag"><Fingerprint size={13} /> PRIVATE BY DESIGN</span></section>

    <div className="section-heading"><div><span className="section-kicker">GETTING STARTED</span><h2>Your next steps</h2></div><span className="muted-caption">A simple path to your first review</span></div>
    <section className="step-grid" aria-label="Getting started">
      {steps.map(({ n, icon: Icon, title, text, to, link }) => <article className="step-card" key={n}><div className="step-top"><span className="step-icon"><Icon size={18} /></span><span className="step-number">{n}</span></div><h3>{title}</h3><p>{text}</p><Link to={to} className="text-link">{link}<ArrowRight size={15} /></Link></article>)}
    </section>

    <section className="overview-grid">
      <div className="surface-card portfolio-overview"><div className="card-heading"><div><span className="section-kicker">PORTFOLIO SNAPSHOT</span><h2>Nothing to report yet</h2></div><span className="subtle-badge">AWAITING DATA</span></div><StatePanel title="Your portfolio will appear here" description="Once you add holdings, this space will show calculated totals and allocation. No sample figures are used." action="Add a portfolio" to="/portfolios" /></div>
      <div className="surface-card connection-card"><div className="card-heading"><div><span className="section-kicker">SYSTEM STATUS</span><h2>Workspace connection</h2></div><span className="connection-pulse" /></div><p className="connection-intro">The dashboard checks the API health endpoint when it loads.</p><ApiStatus /><div className="connection-foot"><span>Health check</span><code>GET /health</code></div></div>
    </section>
    <div className="bottom-note"><span className="bottom-note-mark">i</span><span>This workspace is a research aid. It does not place trades or promise investment outcomes.</span></div>
  </div>;
}

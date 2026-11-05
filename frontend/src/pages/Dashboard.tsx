import { useEffect, useState } from "react";
import { AlertCircle, ArrowRight, FileUp, Fingerprint, LineChart, LoaderCircle, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { AllocationList, formatMoney } from "../components/AllocationList";
import { ApiStatus } from "../components/ApiStatus";
import { AuthGate } from "../components/AuthGate";
import { StatePanel } from "../components/StatePanel";
import { apiGet, apiPost, type Portfolio, type PortfolioAnalytics } from "../services/api";

const steps = [
  { n: "01", icon: FileUp, title: "Add your holdings", text: "Create a portfolio or import a CSV to get started.", to: "/portfolios", link: "Set up portfolio" },
  { n: "02", icon: LineChart, title: "Understand the numbers", text: "See cost basis, allocation, and risk with clear assumptions.", to: "/portfolios", link: "Explore analytics" },
  { n: "03", icon: Sparkles, title: "Research with evidence", text: "Bring company disclosures and sourced facts into view.", to: "/research", link: "Open research" },
];

function DashboardSummary() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [analytics, setAnalytics] = useState<PortfolioAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    apiGet<Portfolio[]>("/portfolios").then(async (items) => {
      if (!active) return;
      const first = items[0];
      if (!first) return;
      setPortfolio(first);
      const summary = await apiPost<PortfolioAnalytics>(`/portfolios/${first.id}/analytics`, { prices: [] });
      if (active) setAnalytics(summary);
    }).catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Could not load the portfolio summary."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  if (loading) return <div className="dashboard-loading"><LoaderCircle className="spin" size={17} />Loading portfolio summary…</div>;
  if (error) return <div className="dashboard-error"><AlertCircle size={15} /><span>{error}</span><Link to="/portfolios">Open portfolios</Link></div>;
  if (!portfolio || !analytics || analytics.positions.length === 0) return <StatePanel title="Your portfolio will appear here" description="Create a portfolio and import holdings to see backend-calculated cost basis and allocation. No sample figures are used." action="Add holdings" to="/portfolios" />;

  return <div className="dashboard-summary-content">
    <div className="dashboard-total-row"><div><span className="summary-label">{portfolio.name} · COST BASIS</span><strong>{formatMoney(analytics.cost_basis_total, analytics.base_currency)}</strong></div><span className={`completion-chip${analytics.complete ? " complete" : " partial"}`}>{analytics.complete ? "Market data complete" : `${analytics.unpriced_position_count} prices missing`}</span></div>
    <div className="dashboard-quick-metrics"><div><span>Market value</span><b>{formatMoney(analytics.market_value_total, analytics.base_currency)}</b></div><div><span>Unrealized P/L</span><b>{formatMoney(analytics.unrealized_pl_total, analytics.base_currency)}</b></div><div><span>Positions</span><b>{analytics.positions.length}</b></div></div>
    <AllocationList title="Sector allocation" entries={analytics.sector_mix} currency={analytics.base_currency} />
    {!analytics.complete && <p className="dashboard-freshness"><AlertCircle size={13} />Market value and market allocation need fresh matching prices.</p>}
    <Link to="/portfolios" className="text-link">View holdings and price status<ArrowRight size={14} /></Link>
  </div>;
}

export function DashboardPage() {
  return <AuthGate><DashboardContent /></AuthGate>;
}

function DashboardContent() {
  return <div className="dashboard-page">
    <section className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line" /> YOUR RESEARCH WORKSPACE</div><h1>Good decisions start<br className="desktop-break" /> with a clearer picture.</h1><p className="welcome-copy">A calm place to understand your portfolio, follow the evidence, and see what is still unknown.</p></div><div className="welcome-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core"><Sparkles size={23} /></div><span className="orbit-point point-one" /><span className="orbit-point point-two" /></div></section>

    <section className="notice-card"><div className="notice-symbol"><ShieldCheck size={19} /></div><div className="notice-copy"><b>Your data, your context</b><p>Calculations use the holdings and prices you provide. Missing or stale inputs stay visible.</p></div><span className="notice-tag"><Fingerprint size={13} /> PRIVATE BY DESIGN</span></section>

    <div className="section-heading"><div><span className="section-kicker">GETTING STARTED</span><h2>Your next steps</h2></div><span className="muted-caption">A simple path to your first review</span></div>
    <section className="step-grid" aria-label="Getting started">
      {steps.map(({ n, icon: Icon, title, text, to, link }) => <article className="step-card" key={n}><div className="step-top"><span className="step-icon"><Icon size={18} /></span><span className="step-number">{n}</span></div><h3>{title}</h3><p>{text}</p><Link to={to} className="text-link">{link}<ArrowRight size={15} /></Link></article>)}
    </section>

    <section className="overview-grid">
      <div className="surface-card portfolio-overview"><div className="card-heading"><div><span className="section-kicker">PORTFOLIO SNAPSHOT</span><h2>Your portfolio</h2></div><span className="subtle-badge">LIVE FROM YOUR DATA</span></div><DashboardSummary /></div>
      <div className="surface-card connection-card"><div className="card-heading"><div><span className="section-kicker">SYSTEM STATUS</span><h2>Workspace connection</h2></div><span className="connection-pulse" /></div><p className="connection-intro">The dashboard checks the API health endpoint when it loads.</p><ApiStatus /><div className="connection-foot"><span>Health check</span><code>GET /health</code></div></div>
    </section>
    <div className="bottom-note"><span className="bottom-note-mark">i</span><span>This workspace is a research aid. It does not place trades or promise investment outcomes.</span></div>
  </div>;
}

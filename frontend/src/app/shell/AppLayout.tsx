import { Activity, ArrowUpRight, BookOpenText, BriefcaseBusiness, CircleHelp, Command, LayoutDashboard, Sparkles } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { ApiStatus } from "../../components/ApiStatus";

const links = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/portfolios", label: "Portfolios", icon: BriefcaseBusiness },
  { to: "/research", label: "Research", icon: BookOpenText },
];

export function AppLayout() {
  const location = useLocation();
  const currentPage = links.find((link) => link.to === location.pathname)?.label ?? "Page";
  return (
    <div className="app-frame">
      <aside className="sidebar">
        <NavLink className="brand" to="/" aria-label="Northstar home">
          <span className="brand-mark"><Sparkles size={18} strokeWidth={2.2} /></span>
          <span className="brand-copy"><strong>northstar</strong><small>INVESTMENT COPILOT</small></span>
        </NavLink>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
              {label === "Overview" && <span className="nav-dot" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><span className="note-icon"><CircleHelp size={16} /></span><div><b>Research with clarity</b><p>Every insight should show its source.</p></div></div>
          <a className="profile" href="mailto:hello@example.com" onClick={(event) => event.preventDefault()}>
            <span className="avatar">N</span><span className="profile-copy"><b>Your workspace</b><small>Personal account</small></span><ArrowUpRight size={15} className="profile-arrow" />
          </a>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><b>{currentPage}</b></div>
          <div className="topbar-right"><span className="topbar-hint"><Command size={13} /> Research workspace</span><ApiStatus compact /></div>
        </header>
        <main className="page-shell"><Outlet /></main>
        <footer className="app-footer"><span><Activity size={13} /> Built for thoughtful decisions</span><span>Research and risk analysis · Not investment advice</span></footer>
      </div>
    </div>
  );
}

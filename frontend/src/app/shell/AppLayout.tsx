import { Activity, BookOpenText, BriefcaseBusiness, CircleHelp, Command, LayoutDashboard, LogOut, Sparkles } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { ApiStatus } from "../../components/ApiStatus";
import { useAuth } from "../AuthContext";

const links = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/portfolios", label: "Portfolios", icon: BriefcaseBusiness },
  { to: "/research", label: "Research", icon: BookOpenText },
  { to: "/chat", label: "Portfolio chat", icon: Command },
  { to: "/reviews", label: "Portfolio reviews", icon: Activity },
];

export function AppLayout() {
  const location = useLocation();
  const { user, signOut } = useAuth();
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
          <div className="sidebar-note"><span className="note-icon"><CircleHelp size={19} /></span><div><b>Your next insight starts here.</b><p>Open a holding to explore the news, weigh the signals and follow the evidence.</p></div></div>
          {user ? <button className="profile profile-button" type="button" onClick={signOut} title="Sign out">
            <span className="avatar">{user.email.slice(0, 1).toUpperCase()}</span><span className="profile-copy"><b>{user.email}</b><small>Sign out</small></span><LogOut size={14} className="profile-arrow" />
          </button> : <div className="profile"><span className="avatar">N</span><span className="profile-copy"><b>Your workspace</b><small>Private account</small></span></div>}
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><b>{currentPage}</b></div>
          <div className="topbar-right"><span className="topbar-hint"><Sparkles size={15} /> Perspective, backed by sources</span><ApiStatus compact /></div>
        </header>
        <main className="page-shell"><Outlet /></main>
        <footer className="app-footer"><span><Activity size={13} /> Built for thoughtful decisions</span><span>Research and risk analysis · Not investment advice</span></footer>
      </div>
    </div>
  );
}

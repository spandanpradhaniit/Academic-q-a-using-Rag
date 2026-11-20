import { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  Bell,
  BrainCircuit,
  ChevronDown,
  FileText,
  HelpCircle,
  Layers3,
  Menu,
  Moon,
  PanelLeftClose,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  Upload,
  X,
} from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Brand } from "../pages/LandingPage";

const primaryNav = [
  { to: "/app/dashboard", label: "Overview", icon: Activity },
  { to: "/app/chat", label: "Ask Scholar", icon: BrainCircuit },
  { to: "/app/documents", label: "Documents", icon: FileText },
  { to: "/app/knowledge", label: "Knowledge base", icon: Layers3 },
  { to: "/app/analytics", label: "Analytics", icon: BarChart3 },
];

export function WorkspaceLayout() {
  const { user } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const title = location.pathname.startsWith("/app/documents/") &&
    location.pathname !== "/app/documents"
    ? "Document details"
    : primaryNav.find((item) => location.pathname.startsWith(item.to))?.label ??
      (location.pathname.includes("/admin")
        ? "Admin overview"
        : "Document details");
  const userInitials =
    user?.name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() ?? "";

  useEffect(() => {
    if (!mobileOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobileOpen]);

  return (
    <div
      className={`workspace ${dark ? "theme-dark" : ""} ${
        collapsed ? "sidebar-collapsed" : ""
      }`}
    >
      {mobileOpen && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}
        aria-label="Workspace navigation"
      >
        <div className="sidebar-top">
          <NavLink
            to="/app/dashboard"
            className="sidebar-brand"
            aria-label="Scholar workspace home"
          >
            <Brand />
          </NavLink>
          <button
            className="icon-button sidebar-collapse"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setCollapsed(!collapsed)}
          >
            <PanelLeftClose size={17} />
          </button>
          <button
            className="icon-button mobile-close"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <X size={18} />
          </button>
        </div>
        <button
          className="workspace-switch"
          onClick={() => navigate("/app/dashboard")}
        >
          <span className="workspace-avatar">R</span>
          <span className="workspace-switch-text">
            <b>Research workspace</b>
            <small>Personal library</small>
          </span>
          <ChevronDown size={14} />
        </button>
        <button
          className="new-chat-button"
          onClick={() => navigate("/app/chat?new=1")}
        >
          <Plus size={16} />
          <span>New conversation</span>
        </button>
        <nav className="nav-group" aria-label="Workspace">
          <span className="nav-caption">WORKSPACE</span>
          {primaryNav.map(({ to, label, icon: Icon }) => (
            <NavLink
              to={to}
              key={to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
              title={collapsed ? label : undefined}
            >
              <Icon size={17} />
              <span className="nav-label">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-bottom">
          <NavLink
            to="/app/settings"
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            onClick={() => setMobileOpen(false)}
          >
            <Settings size={17} />
            <span className="nav-label">Settings</span>
          </NavLink>
          <NavLink
            to="/app/admin"
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            onClick={() => setMobileOpen(false)}
          >
            <ShieldCheck size={17} />
            <span className="nav-label">Admin</span>
            <span className="admin-pill">DEMO</span>
          </NavLink>
          <button
            className="profile-row"
            onClick={() => navigate("/app/settings")}
          >
            <span className="profile-avatar">{user?.avatar || userInitials}</span>
            <span className="profile-info">
              <b>{user?.name || "Account"}</b>
              {user?.email && <small>{user.email}</small>}
            </span>
            <ChevronDown size={14} />
          </button>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={19} />
            </button>
            <div className="breadcrumbs">
              <span>Workspace</span>
              <span>/</span>
              <b>{title}</b>
            </div>
          </div>
          <div className="topbar-actions">
            <div className={`global-search ${searchOpen ? "search-open" : ""}`}>
              <Search size={15} />
              <input
                aria-label="Search your workspace"
                placeholder="Search anything..."
                value={search}
                onFocus={() => setSearchOpen(true)}
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(event) =>
                  event.key === "Enter" &&
                  navigate(`/app/documents?q=${encodeURIComponent(search)}`)
                }
                onBlur={() => {
                  if (!search) setSearchOpen(false);
                }}
              />
            </div>
            <span className="topbar-divider" />
            <div className="notification-wrap">
              <button
                className="icon-button topbar-icon"
                aria-label="Notifications"
                aria-expanded={notifications}
                onClick={() => setNotifications(!notifications)}
              >
                <Bell size={17} />
                <i />
              </button>
              {notifications && (
                <div className="notification-menu">
                  <b>You're all caught up</b>
                  <p>Your research library is up to date.</p>
                </div>
              )}
            </div>
            <button
              className="icon-button topbar-icon theme-toggle"
              aria-label={`Switch to ${dark ? "light" : "dark"} mode`}
              aria-pressed={dark}
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button
              className="topbar-upload"
              onClick={() => navigate("/app/documents?upload=1")}
            >
              <Upload size={15} />
              <span>Upload PDF</span>
            </button>
          </div>
        </header>
        <div className="page-content">
          <Outlet />
        </div>
        <footer className="workspace-footer">
          <span>
            <span className="status-online" /> All systems operational
          </span>
          <span>
            Scholar AI <i>·</i> Grounded in your sources
          </span>
          <button onClick={() => navigate("/app/settings")}>
            <HelpCircle size={13} /> Help & feedback
          </button>
        </footer>
      </div>
    </div>
  );
}

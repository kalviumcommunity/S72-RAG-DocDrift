import {
  Bell,
  CircleHelp,
  Command,
  RefreshCw,
  Search,
} from "lucide-react";
import { useState } from "react";
import { navigateTo } from "../../utils/navigation";

const Navbar = ({ activePage = "Home" }: { activePage?: string }) => {
  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState("");
  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2200);
  };

  return (
    <header className="navbar">
      {/* Left */}
      <div className="navbar-left">
        <div className="brand">
          <div className="brand-mark">
            <span />
            <span />
            <span />
            <span />
          </div>

          <span className="brand-name">DocDrift</span>
        </div>

        <div className="global-search">
          <Search size={13} strokeWidth={1.8} />

          <span>{activePage === "Docs" ? "Filter indexed specs..." : "Search endpoints, RFCs..."}</span>

          <div className="command-key">
            <Command size={9} />
            <span>K</span>
          </div>
        </div>
      </div>

      {/* Right */}
      <div className="navbar-right">
        <nav className="nav-links">
          <a href="/" onClick={(event) => { event.preventDefault(); navigateTo("/"); }} className={activePage === "Home" ? "active" : ""}>
            Home
          </a>

          <a href="/chat" onClick={(event) => { event.preventDefault(); navigateTo("/chat"); }} className={activePage === "Chat" ? "active" : ""}>Chat</a>
          <a href="/docs" onClick={(event) => { event.preventDefault(); navigateTo("/docs"); }} className={activePage === "Docs" ? "active" : ""}>Docs</a>
          <a href="/settings" onClick={(event) => { event.preventDefault(); navigateTo("/settings"); }} className={activePage === "Settings" ? "active" : ""}>Settings</a>
        </nav>

        <div className="version-badge">
          <span className="version-dot" />
          <span>v2.4.0</span>
        </div>

        <button className="sync-button" type="button" onClick={() => { setSyncing(true); window.setTimeout(() => setSyncing(false), 1200); showNotice("Documentation sync complete"); }}>
          <RefreshCw size={11} />
          <span>{syncing ? "Syncing..." : "Sync Docs"}</span>
        </button>

        <button className="icon-button" type="button" aria-label="Notifications" onClick={() => showNotice("No new notifications")}>
          <Bell size={13} />
        </button>

        <button className="icon-button" type="button" aria-label="Help" onClick={() => showNotice("Help center is available after backend setup")}>
          <CircleHelp size={14} />
        </button>

        <div className="avatar">S</div>
      </div>
      {notice && <div className="app-notice" role="status">{notice}</div>}
    </header>
  );
};

export default Navbar;
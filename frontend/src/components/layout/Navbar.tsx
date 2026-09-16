import {
  Bell,
  CircleHelp,
  Command,
  RefreshCw,
  Search,
} from "lucide-react";

const Navbar = () => {
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

          <span>Search endpoints, RFCs...</span>

          <div className="command-key">
            <Command size={9} />
            <span>K</span>
          </div>
        </div>
      </div>

      {/* Right */}
      <div className="navbar-right">
        <nav className="nav-links">
          <a href="#" className="active">
            Home
          </a>

          <a href="#">Chat</a>
          <a href="#">Docs</a>
          <a href="#">Settings</a>
        </nav>

        <div className="version-badge">
          <span className="version-dot" />
          <span>v2.4.0</span>
        </div>

        <button className="sync-button">
          <RefreshCw size={11} />
          <span>Sync Docs</span>
        </button>

        <button className="icon-button" aria-label="Notifications">
          <Bell size={13} />
        </button>

        <button className="icon-button" aria-label="Help">
          <CircleHelp size={14} />
        </button>

        <div className="avatar">S</div>
      </div>
    </header>
  );
};

export default Navbar;
import { useEffect, useState } from "react";
import {
  Check,
  ChevronDown,
  Clipboard,
  Edit3,
  KeyRound,
  Monitor,
  Moon,
  Save,
  Settings2,
  Sun,
  Users,
  X,
} from "lucide-react";

const Settings = () => {
  const [teamName, setTeamName] = useState("Acme Engineering Core");
  const [theme, setTheme] = useState(() => localStorage.getItem("docdrift-theme") || "Light");
  const [apiKey, setApiKey] = useState("sk_live_docdrift_98f••••••••••••••7a2");
  const [version, setVersion] = useState("v3 Default (Current Stable LTS)");
  const [editingTeam, setEditingTeam] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const themeClass = theme === "Dark" ? "theme-dark" : theme === "Light" ? "theme-light" : "";
    document.documentElement.classList.remove("theme-dark", "theme-light");
    if (themeClass) document.documentElement.classList.add(themeClass);
    localStorage.setItem("docdrift-theme", theme);
  }, [theme]);

  const saveSettings = () => {
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1600);
  };

  const cancelSettings = () => {
    setTeamName("Acme Engineering Core");
    setTheme("Light");
    setVersion("v3 Default (Current Stable LTS)");
    setEditingTeam(false);
  };

  const copyApiKey = async () => {
    try { await navigator.clipboard?.writeText(apiKey); } catch { /* Preview clipboard can be unavailable. */ }
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1400);
  };

  const regenerateKey = () => {
    setApiKey(`sk_live_docdrift_${Math.random().toString(36).slice(2, 8)}••••••••••••••${Math.random().toString(36).slice(2, 5)}`);
  };

  return (
    <main className="settings-page">
      <div className="settings-content">
        <div className="settings-eyebrow"><Settings2 size={12} /> WORKSPACE CONFIGURATION</div>
        <h1>Settings</h1>
        <p className="settings-intro">Manage team access parameters, secure API infrastructure credentials, and client runtime preferences.</p>

        <section className="settings-card workspace-card">
          <div className="settings-card-heading"><span className="settings-icon"><Users size={14} /></span><div><h2>Workspace &amp; Team</h2><p>Organization profile identity and public access route URL</p></div><span className="plan-badge">Active Pro</span></div>
          <div className="settings-fields three-fields">
            <label>Team Name<input value={teamName} disabled={!editingTeam} onChange={(event) => setTeamName(event.target.value)} /></label>
            <label>Visible to team<div className="readonly-field">Workspace Slug<input value="app.docdrift.io/acme-eng" readOnly /></div></label>
            <label>Canonical route<div className="route-field">app.docdrift.io/<strong>acme-eng</strong><Clipboard size={13} /></div></label>
          </div>
          <button className="field-edit" type="button" aria-label="Edit team name" onClick={() => setEditingTeam((editing) => !editing)}><Edit3 size={13} /></button>
        </section>

        <section className="settings-card api-card">
          <div className="settings-card-heading"><span className="settings-icon"><KeyRound size={14} /></span><div><h2>API &amp; Model Configuration</h2><p>Bearer authentication tokens and live production edge endpoints</p></div><span className="environment-badge">Production</span></div>
          <div className="api-key-row"><label>API Key<div className="api-key-value"><code>{apiKey}</code><span className="active-badge">Active</span></div></label><span className="key-meta">Created 14 days ago · Never expires</span><button type="button" className="small-action" onClick={copyApiKey}><Clipboard size={12} /> Copy</button><button type="button" className="regenerate" onClick={regenerateKey}><X size={12} /> Regenerate Key</button></div>
          <label className="endpoint-label">API Endpoint URL<div className="endpoint-field"><span>REST</span> https://api.docdrift.io/v1 <code>200 OK</code></div></label>
        </section>

        <section className="settings-card appearance-card">
          <div className="settings-card-heading"><span className="settings-icon"><Sun size={14} /></span><div><h2>Appearance &amp; Preferences</h2><p>Interface theme modes and default specification schema targets</p></div></div>
          <div className="appearance-fields">
            <div><label>Interface Theme</label><div className="theme-options">{[["Light", Sun], ["Dark", Moon], ["System default", Monitor]].map(([label, Icon]) => <button type="button" key={label as string} className={theme === label ? "selected" : ""} onClick={() => setTheme(label as string)}><Icon size={13} />{label as string}</button>)}</div><small>Currently active: <strong>{theme} Slate</strong> high-density developer canvas.</small></div>
            <div><label>Default Version Preference</label><button className="version-preference" type="button" onClick={() => setVersion((current) => current.startsWith("v3") ? "v2 Legacy Compatibility" : "v3 Default (Current Stable LTS)")}>{version} <ChevronDown size={13} /></button><small><span className="preference-dot" />Default index queries will automatically resolve to {version.startsWith("v3") ? "v3" : "v2"}</small></div>
          </div>
        </section>

        <div className="settings-actions"><span><Check size={13} /> Workspace changes take effect across instances instantly</span><button type="button" className="cancel-button" onClick={cancelSettings}>Cancel</button><button type="button" className="save-button" onClick={saveSettings}>{saved ? <Check size={13} /> : <Save size={13} />} {saved ? "Saved" : "Save Changes"}</button></div>
      </div>
    </main>
  );
};

export default Settings;
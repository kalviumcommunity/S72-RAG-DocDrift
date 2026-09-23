import {
  ArrowDownToLine,
  Check,
  CircleHelp,
  FileCode2,
  FileText,
  Filter,
  MoreVertical,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
  Waypoints,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

const documents = [
  { name: "Core REST API Reference", path: "/specs/openapi-v3.2.json · 14.2 MB", type: "API Doc", version: "v3.2", date: "Oct 24, 2024", icon: FileText, tone: "mint", live: true },
  { name: "Authentication & SSO Migration Guide", path: "/guides/auth-sso-upgrade.md · 2.8 MB", type: "Migration Guide", version: "v2.4.0 → v3.0", date: "Nov 02, 2024", icon: FileCode2, tone: "gold" },
  { name: "Release Changelog 2024", path: "/changelog/2024-complete.md · 1.1 MB", type: "Changelog", version: "v3.1.4", date: "2 hours ago", icon: Waypoints, tone: "green" },
  { name: "Webhooks & Events Spec", path: "/specs/events-async.yaml · 8.5 MB", type: "API Doc", version: "v3.2", date: "Oct 18, 2024", icon: Waypoints, tone: "blue" },
  { name: "Python & TypeScript SDK Manual", path: "/sdks/multi-language-core.md · 21.6 MB", type: "SDK Spec", version: "v1.8", date: "Sep 30, 2024", icon: FileText, tone: "yellow" },
];

const Docs = () => {
  const [documentList, setDocumentList] = useState(documents);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [versionFilter, setVersionFilter] = useState("ALL");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const uploadInput = useRef<HTMLInputElement>(null);
  const visibleDocuments = useMemo(() => documentList.filter((document) => {
    const matchesSearch = `${document.name} ${document.path}`.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === "ALL" || document.type === typeFilter;
    const matchesVersion = versionFilter === "ALL" || document.version.toLowerCase().includes(versionFilter.toLowerCase());
    return matchesSearch && matchesType && matchesVersion;
  }), [documentList, search, typeFilter, versionFilter]);
  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2200);
  };
  const downloadDocuments = () => {
    const csv = ["name,type,version,date", ...visibleDocuments.map((document) => `${document.name},${document.type},${document.version},${document.date}`)].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "docdrift-documents.csv";
    link.click();
    URL.revokeObjectURL(url);
    showNotice("Document list downloaded");
  };
  const handleUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setDocumentList((current) => [{ name: file.name.replace(/\.[^/.]+$/, ""), path: `/uploads/${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`, type: "API Doc", version: "v3.2", date: "Just now", icon: FileText, tone: "mint", live: true }, ...current]);
    showNotice(`${file.name} added to the index`);
    event.target.value = "";
  };

  return <main className="docs-page">
    <section className="docs-heading">
      <div>
        <h1>Document Management <span>18 total</span></h1>
        <p>Manage and index API specifications, OpenAPI schemas, markdown guides, and release changelogs.</p>
      </div>
      <input ref={uploadInput} hidden type="file" accept=".json,.yaml,.yml,.md,.txt" onChange={handleUpload} />
      <button className="upload-button" type="button" onClick={() => uploadInput.current?.click()}><Plus size={14} /> Upload New Document</button>
    </section>

    <section className="document-table-shell">
      <div className="document-controls">
        <label className="document-search"><Search size={12} /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search documents by title, repo, or hash..." /></label>
        <div className="filter-group"><span>TYPE:</span>{["ALL", "API Doc", "Migration Guide", "Changelog"].map((filter) => <button className={typeFilter === filter ? "selected" : ""} type="button" key={filter} onClick={() => { setTypeFilter(filter); setPage(1); }}>{filter === "API Doc" ? "API Reference" : filter}</button>)}</div>
        <div className="filter-group version-filter"><span>VERSION:</span>{["ALL", "v1", "v2", "v3"].map((filter) => <button className={versionFilter === filter ? "selected" : ""} type="button" key={filter} onClick={() => { setVersionFilter(filter); setPage(1); }}>{filter}</button>)}</div>
        <button className="table-icon-button" type="button" aria-label="Download documents" onClick={downloadDocuments}><ArrowDownToLine size={13} /></button>
        <button className="table-icon-button" type="button" aria-label="Reset filters" onClick={() => { setSearch(""); setTypeFilter("ALL"); setVersionFilter("ALL"); setPage(1); }}><Filter size={13} /></button>
      </div>

      <div className="document-table" role="table" aria-label="Indexed documents">
        <div className="document-row document-header" role="row"><span>DOCUMENT NAME</span><span>TYPE</span><span>VERSION</span><span>DATE ADDED</span><span>ACTIONS</span></div>
        {visibleDocuments.map((document) => {
          const Icon = document.icon;
          return <div className="document-row" role="row" key={document.name}>
            <div className="document-name"><span className={`document-icon ${document.tone}`}><Icon size={12} /></span><div><strong>{document.name}</strong>{document.live && <em>LIVE</em>}<small>{document.path}</small></div></div>
            <span><b className={`type-pill ${document.tone}`}>{document.type}</b></span>
            <span><b className={`version-pill ${document.version.includes("→") ? "transition" : ""}`}>{document.version}</b></span>
            <span className="document-date">{document.date}</span>
            <div className="document-actions"><button type="button" onClick={() => showNotice(`${document.name} re-sync queued`)}><RefreshCw size={10} /> Re-sync</button><button type="button" onClick={() => showNotice(`Previewing ${document.name}`)}><Search size={10} /> View raw</button><button className="more-button" type="button" aria-label={`More actions for ${document.name}`} onClick={() => showNotice(`More actions for ${document.name}`)}><MoreVertical size={13} /></button></div>
          </div>;
        })}
      </div>
      <footer className="table-footer"><span>Showing {visibleDocuments.length} of 18 documents <b>•</b> Total size: 48.2 MB</span><div><button type="button" disabled={page === 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</button>{[1, 2, 3, 4].map((number) => <button className={page === number ? "page-active" : ""} type="button" key={number} onClick={() => setPage(number)}>{number}</button>)}<button type="button" disabled={page === 4} onClick={() => setPage((current) => Math.min(4, current + 1))}>Next</button></div></footer>
    </section>

    <section className="docs-status-grid">
      <article><span className="status-card-icon cyan"><Sparkles size={13} /></span><div><h2>Auto-Sync Vector Index</h2><p>All 5 active documentation trees are currently synchronized with Pinecone and Qdrant clusters.</p></div></article>
      <article><span className="status-card-icon mint"><FileText size={13} /></span><div><h2>Changelog Parser Active</h2><p>Semantic version drift detection flags breaking changes in AST payloads across all migrations.</p></div></article>
      <article><span className="status-card-icon gold"><Waypoints size={13} /></span><div><h2>Webhook Ingestion Endpoint</h2><p>GitHub Action workflows trigger automatic re-indexing upon any PR merge into default branch.</p></div></article>
    </section>

    <div className="docs-footer-status"><span><Check size={11} /> All systems operational</span><span><Settings2 size={11} /> Last indexed 2 mins ago</span><span><CircleHelp size={11} /> Need help?</span></div>
    {notice && <div className="app-notice docs-notice" role="status">{notice}</div>}
  </main>;
};

export default Docs;
import { useState } from "react";
import {
  ArrowUp,
  Check,
  ChevronDown,
  CircleHelp,
  Code2,
  Copy,
  ExternalLink,
  FileText,
  GitBranch,
  History,
  Menu,
  MoreVertical,
  Plus,
  Search,
  Send,
  SlidersHorizontal,
  Sparkles,
  Terminal,
  X,
} from "lucide-react";
import { navigateTo } from "../utils/navigation";

const threads = [
  ["Idempotency key TTL specs", "2h ago"],
  ["OAuth2 PKCE flow in CLI", "Yesterday"],
  ["gRPC streaming error codes", "Mon"],
  ["Rate limit headers delta v2.3", "Sun"],
];

const Chat = () => {
  const [question, setQuestion] = useState("");
  const [sentQuestion, setSentQuestion] = useState(
    new URLSearchParams(window.location.search).get("q") || "How has the signature validation header changed from Webhooks v2 to v3, and what is the new canonical HMAC algorithm?",
  );
  const [copied, setCopied] = useState(false);
  const [inspectorVisible, setInspectorVisible] = useState(true);

  const submitQuestion = () => {
    if (!question.trim()) return;
    setSentQuestion(question.trim());
    setQuestion("");
  };

  const copyCode = async () => {
    try {
      await navigator.clipboard?.writeText("const expectedSig = sigPart.replace('v3=', '');");
    } catch {
      // Clipboard access is unavailable on some local preview origins.
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };

  return (
    <main className="chat-page">
      <aside className="chat-sidebar">
        <button className="new-query-button" type="button" onClick={() => { setQuestion(""); setSentQuestion("Ask a new question about your indexed documentation."); }}>
          <Plus size={14} />
          <span>New Query</span>
          <span className="shortcut">⌘↵</span>
        </button>

        <div className="sidebar-section">
          <div className="sidebar-label">ACTIVE SESSION <SlidersHorizontal size={11} /></div>
          <div className="active-session">
            <span className="session-icon"><FileText size={11} /></span>
            <span>Migrating to Webhook v3</span>
            <span className="online-dot" />
          </div>
        </div>

        <div className="sidebar-section recent-section">
          <div className="sidebar-label">RECENT THREADS</div>
          {threads.map(([title, time]) => (
            <button className="thread-item" key={title} type="button" onClick={() => setSentQuestion(title)}>
              <History size={12} />
              <span>{title}</span>
              <small>{time}</small>
            </button>
          ))}
        </div>

        <div className="sidebar-section synced-section">
          <div className="sidebar-label">SYNCED SOURCES <span>3 Indexed</span></div>
          <div className="source-item"><span className="source-dot" />api-reference-v3 <small>2m ago</small></div>
          <div className="source-item"><span className="source-dot" />migration-guide-v3 <small>1h ago</small></div>
        </div>

        <div className="sidebar-bottom">
          <button type="button" onClick={() => navigateTo("/settings")}><Terminal size={13} />API Keys</button>
          <button type="button" onClick={() => navigateTo("/docs")}><FileText size={13} />Documentation</button>
        </div>
      </aside>

      <section className="conversation-panel">
        <header className="conversation-header">
          <div className="conversation-title">
            <h1>Migrating to Webhook v3 <span>RFC-8403</span></h1>
            <div className="commit-meta"><GitBranch size={11} /> Branch: <strong>main</strong> <ChevronDown size={11} /> · commit <strong>e9c7c81</strong> <MoreVertical size={13} /></div>
          </div>
          <button className="mobile-menu" type="button" aria-label="Toggle citation inspector" onClick={() => setInspectorVisible((visible) => !visible)}><Menu size={16} /></button>
        </header>

        <div className="conversation-scroll">
          <div className="version-select">v3.8 <ChevronDown size={10} /></div>
          <div className="question-bubble">
            <p>{sentQuestion}</p>
            <small>Delivered 10:42 AM · <strong>Context: v3.8 (Active)</strong></small>
          </div>

          <article className="answer-card">
            <div className="answer-heading"><span className="doc-icon"><FileText size={13} /></span><h2>Webhook v3 Signature Specification</h2><span className="verified"><Check size={11} /> Verified Canonical</span></div>
            <p>In Webhook v3, the legacy header <code>X-DocDrift-Signature</code> has been superseded by <a href="#citation">DocDrift-Signature-SHA256</a>. Additionally, payload timestamp replay defenses are now strictly enforced via a millisecond header.</p>
            <ul className="answer-points">
              <li><Check size={13} /> <span><strong>HMAC Algorithm:</strong> Standardized to <mark>HMAC-SHA256</mark> (replaces SHA-1 fallback).</span></li>
              <li><Check size={13} /> <span><strong>Canonical String:</strong> Constructed as <mark>{"${timestamp}.${payload}"}</mark>.</span></li>
              <li><Check size={13} /> <span><strong>Tolerance Window:</strong> Timestamps exceeding 300,000ms (5 min) skew must be rejected with HTTP 401.</span></li>
            </ul>

            <div className="code-block">
              <div className="code-toolbar"><span>NODE.JS (TYPESCRIPT) <i>verify-signature.ts</i></span><button type="button" onClick={copyCode}>{copied ? <Check size={12} /> : <Copy size={12} />} {copied ? "Copied" : "Copy"}</button></div>
              <pre><code>{`// 1. Extract signature and timestamp headers
import { createHmac, timingSafeEqual } from "node:crypto";

export function verifyWebhookV3({
  payload: string,
  signatureHeader: string,
  secret: string
}): boolean {
  const [ts, sigPart] = signatureHeader.split(".");
  const timestamp = ts.replace("t=", "");
  const expectedSig = sigPart.replace("v3=", "");`}</code></pre>
            </div>
            <div className="answer-sources"><span><Sparkles size={12} /> Synthesized from 3 sources</span><a href="#citation">View citations <ArrowUp size={11} /></a></div>
          </article>
        </div>

        <div className="composer-wrap">
          <div className="composer">
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submitQuestion(); } }} placeholder="Ask a question about your docs or APIs..." rows={2} />
            <div className="composer-toolbar"><div><button type="button" onClick={() => setQuestion((value) => `${value} Include a code snippet.`)}><Code2 size={12} />Snippet</button><button type="button" onClick={() => setQuestion((value) => `${value} Return the JSON schema.`)}><span className="json-icon">{}</span>JSON Schema</button><button type="button" onClick={() => setQuestion((value) => `${value} Link the reference documentation.`)}><FileText size={12} />Ref doc</button></div><span className="composer-hint">⌘↵ to send</span><button className="send-button" type="button" onClick={submitQuestion}>Send <Send size={12} /></button></div>
          </div>
          <div className="engine-status"><span className="status-live" /> RAG Engine: Hybrid Dense-Vector + AST <span>Latency: 480ms · Zero Hallucination Guardrails</span><span>Lexical</span><span className="status-active">Active</span></div>
        </div>
      </section>

      <aside className={`inspector-panel ${inspectorVisible ? "" : "inspector-hidden"}`} id="citation">
        <div className="inspector-header"><h2><Search size={14} /> Citation Inspector</h2><span>Live</span></div>
        <div className="inspector-content">
          <div className="inspector-label">SELECTED SOURCE EXCERPT <ExternalLink size={12} /></div>
          <div className="excerpt-card"><a href="#citation">docs/webhooks/v3/auth.md</a><p>“Starting with Webhooks v3, clients must reject webhook events where the signed unix timestamp differs from current system clock by greater than 300 seconds.”</p><small>Section: 5.4 Replay Attacks <strong>100% Match</strong></small></div>
          <div className="inspector-label mutation-label">PAYLOAD KEY MUTATIONS</div>
          <div className="mutation-card"><div><code>event_type</code><span>type</span></div><p>Flattened event taxonomy for faster proto serialization</p></div>
          <div className="mutation-card"><div><code>occurred_at</code><span>timestamp_ms</span></div><p>ISO 8601 string converted to 64-bit integer timestamp</p></div>
          <div className="drift-alert"><div><Sparkles size={13} /> Automated Drift Check</div><p>Your production webhook receiver has not registered any v3 payloads yet. Dual emission active on project.</p></div>
        </div>
        <div className="inspector-footer"><CircleHelp size={12} /> Inspector updates as citations are selected</div>
        <button className="close-inspector" type="button" aria-label="Close inspector" onClick={() => setInspectorVisible(false)}><X size={14} /></button>
      </aside>
    </main>
  );
};

export default Chat;
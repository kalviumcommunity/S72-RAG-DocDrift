import SearchBar from "../components/home/SearchBar";
import SuggestedQueryCard from "../components/home/SuggestedQueryCard";
import { suggestedQueries } from "../data/mockData";

const Home = () => {
  return (
    <main className="home-page">
      {/* Sync Status */}
      <div className="sync-badge">
        <span className="sync-dot" />

        <span>Multi-Version Sync Enabled</span>

        <span className="sync-divider">/</span>

        <span className="sync-version">
          3.1.0-rc4 Live
        </span>
      </div>

      {/* Hero */}
      <section className="hero-section">
        <h1>
          Search documentation with version
          <br />
          intelligence
        </h1>

        <p>
          Query seamlessly across interconnected API specifications,
          deprecation logs, and
          <br />
          cross-framework migration guides with deterministic source citations.
        </p>
      </section>

      {/* Search */}
      <SearchBar />
      <section className="suggested-section">

        <div className="section-heading">
            <span>
            SUGGESTED QUERIES & DIFF INSPECTIONS
            </span>

            <span className="instant-answer">
            ✦ Instant Synthesized Answers
            </span>
        </div>

        <div className="query-grid">
            {suggestedQueries.map((query) => (
            <SuggestedQueryCard
                key={`${query.type}-${query.version}`}
                query={query}
            />
            ))}
        </div>

        </section>

        <footer className="home-footer">
        <div className="footer-left">

            <div className="footer-item">
            <span className="footer-status-dot"></span>
            <span>42 doc sets indexed</span>
            </div>

            <div className="footer-item">
            <span>3 versions synced</span>
            <span className="footer-versions">
                (v1, v2, v3)
            </span>
            </div>

        </div>

        <div className="footer-right">

            <div className="footer-item">
            <span>◷</span>
            <span>Re-indexed 3 mins ago</span>
            </div>

            <div className="footer-item footer-ready">
            <span>▣</span>
            <span>
                Vector Store: <span>Ready</span>
            </span>
            </div>

        </div>
        </footer>
            </main>
        );
        };

export default Home;
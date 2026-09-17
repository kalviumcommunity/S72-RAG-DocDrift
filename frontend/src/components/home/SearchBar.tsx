import { ArrowRight, Command, Search, Loader2 } from "lucide-react";
import { useState } from "react";
import api from "../../api";

const SearchBar = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setHasSearched(true);
    try {
      const response = await api.get('/search', {
        params: { query_string: query, top_k: 5 }
      });
      setResults(response.data);
    } catch (error) {
      console.error("Error searching:", error);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="search-container">
      <div className="main-search">
        <Search
          className="main-search-icon"
          size={16}
          strokeWidth={1.8}
        />

        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              handleSearch();
            }
          }}
          placeholder="Ask any question across your API docs, changelogs, or guides..."
        />

        <div className="search-shortcut">
          <Command size={9} />
          <span>K</span>
        </div>

        <button
          className="search-button"
          onClick={handleSearch}
          disabled={isLoading}
        >
          {isLoading ? (
            <Loader2 className="animate-spin" size={13} />
          ) : (
            <>
              <span>Search Docs</span>
              <ArrowRight size={13} />
            </>
          )}
        </button>
      </div>
      
      {/* Search Results Dropdown */}
      {hasSearched && (
        <div className="search-results" style={{ marginTop: '1rem', background: '#fff', borderRadius: '8px', padding: '1rem', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}>
          {isLoading && <p>Loading results...</p>}
          {!isLoading && results.length === 0 && <p>No results found for "{query}".</p>}
          {!isLoading && results.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {results.map((res: any, idx: number) => (
                <div key={idx} style={{ borderBottom: '1px solid #eee', paddingBottom: '0.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                    <strong>{res.section_header || res.file_name || 'Document'}</strong>
                    <span style={{ fontSize: '0.8rem', color: '#666', background: '#f0f0f0', padding: '2px 6px', borderRadius: '4px' }}>
                      {res.doc_type} | {res.version}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.9rem', color: '#444', margin: 0, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {res.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SearchBar;
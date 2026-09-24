import { ArrowRight, Command, Search } from "lucide-react";
import { useState } from "react";
import { navigateTo } from "../../utils/navigation";

const SearchBar = () => {
  const [query, setQuery] = useState("");

  const handleSearch = () => {
    const encodedQuery = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : "";
    navigateTo(`/chat${encodedQuery}`);
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
          type="button"
          onClick={handleSearch}
        >
          <span>Search Docs</span>
          <ArrowRight size={13} />
        </button>
      </div>
    </div>
  );
};

export default SearchBar;
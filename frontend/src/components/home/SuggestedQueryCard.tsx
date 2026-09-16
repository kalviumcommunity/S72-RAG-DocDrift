import { ArrowUpRight } from "lucide-react";
import type { SuggestedQuery } from "../../data/mockData";

interface SuggestedQueryCardProps {
  query: SuggestedQuery;
}

const SuggestedQueryCard = ({
  query,
}: SuggestedQueryCardProps) => {
  return (
    <button
      type="button"
      className={`query-card ${query.accent}`}
      onClick={() => {
        console.log("Selected:", query.question);
      }}
    >
      <div className="query-card-top">
        <div className="query-label">
          <span>{query.type}</span>
          <span>· {query.version}</span>
        </div>

        <ArrowUpRight
          size={13}
          strokeWidth={1.7}
          className="query-arrow"
        />
      </div>

      <p className="query-question">
        {query.question}
      </p>

      <p className="query-meta">
        {query.metadata}
      </p>
    </button>
  );
};

export default SuggestedQueryCard;
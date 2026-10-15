import React, { useState } from "react";
import type { Fact } from "../api/types";
import "./FactChip.css";

interface FactChipProps {
  factId: string;
  fact?: Fact;
}

export const FactChip: React.FC<FactChipProps> = ({ factId, fact }) => {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div
      className="fact-chip-wrapper"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onFocus={() => setShowTooltip(true)}
      onBlur={() => setShowTooltip(false)}
    >
      <button
        type="button"
        className={`fact-chip ${fact?.estimate ? "fact-chip-estimate" : ""}`}
        aria-label={`Dẫn chứng fact ${factId}: ${fact?.text || ""}`}
      >
        <span>{factId}</span>
        {fact?.estimate && <span style={{ fontSize: "10px" }}>*</span>}
      </button>

      {showTooltip && (
        <div className="fact-chip-tooltip" role="tooltip">
          <div className="fact-chip-tooltip-header">
            <span>{fact ? `${fact.metric}${fact.entity ? ` (${fact.entity})` : ""}` : factId}</span>
            {fact?.estimate && <span className="fact-chip-tooltip-estimate">Ước tính</span>}
          </div>
          <div className="fact-chip-tooltip-text">
            {fact ? fact.text : `Dẫn chứng sự thật mã ${factId}`}
          </div>
        </div>
      )}
    </div>
  );
};

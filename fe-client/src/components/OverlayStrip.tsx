import React from "react";
import type { GameState } from "../types/gameTypes";

interface OverlayStripProps {
  gameState: GameState & {
    runId?: string;
    providerName?: string;
    modelName?: string;
  };
}

const OverlayStrip: React.FC<OverlayStripProps> = ({ gameState }) => {
  const runId = gameState.runId || "";
  return (
    <div className="overlay-strip">
      <div className="overlay-item">
        <span>Run</span>
        {runId || "—"}
      </div>
      <div className="overlay-item">
        <span>Provider</span>
        {gameState.providerName || "—"}
      </div>
      <div className="overlay-item">
        <span>Model</span>
        {gameState.modelName || "—"}
      </div>
    </div>
  );
};

export default OverlayStrip;

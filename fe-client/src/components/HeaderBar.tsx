import React from "react";
import type { GameState } from "../types/gameTypes";

interface HeaderBarProps {
  gameState: GameState;
  wsConnected: boolean;
}

const HeaderBar: React.FC<HeaderBarProps> = ({ gameState, wsConnected }) => {
  const gameTitle =
    ((gameState as Record<string, unknown>).game_title as string) ||
    ((gameState as Record<string, unknown>).gameTitle as string) ||
    "Fire Emblem GBA";

  return (
    <div className="header-bar">
      <div className="header-section">
        <h1>Fire Emblem AI</h1>
        <span className="subtitle">{gameTitle}</span>
      </div>

      <div className="header-section">
        <div className="status-item">
          <span className="label">Chapter:</span>
          <span className="value">{gameState.chapterId || "Unknown"}</span>
        </div>
        <div className="status-item">
          <span className="label">Turn:</span>
          <span className="value">{gameState.turnNumber || 0}</span>
        </div>
        <div className="status-item">
          <span className="label">Phase:</span>
          <span className="value phase">{gameState.phase || "Player"}</span>
        </div>
      </div>

      <div className="header-section">
        <div className="status-item">
          <span className="label">Actions:</span>
          <span className="value">{gameState.actions || 0}</span>
        </div>
        <div className="status-item">
          <span className="label">Tokens:</span>
          <span className="value">{gameState.tokensUsed ?? 0}</span>
        </div>
        <div className="status-item">
          <span className="label">Model:</span>
          <span className="value">{gameState.modelName || "Unknown"}</span>
        </div>
        {gameState.llmMetrics && (
          <div className="status-item">
            <span className="label">LLM p95:</span>
            <span className="value">
              {typeof gameState.llmMetrics.p95LatencySec === "number"
                ? `${gameState.llmMetrics.p95LatencySec.toFixed(2)}s`
                : "-"}
              {typeof gameState.llmMetrics.successRate === "number"
                ? ` (${Math.round(gameState.llmMetrics.successRate * 100)}%)`
                : ""}
            </span>
          </div>
        )}
        <div
          className={`connection-status ${wsConnected ? "connected" : "disconnected"}`}
        >
          {wsConnected ? "● Connected" : "○ Disconnected"}
        </div>
      </div>
    </div>
  );
};

export default HeaderBar;

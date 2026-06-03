import React from "react";
import type { GameState } from "../types/gameTypes";

interface GameDisplayProps {
  gameState: GameState;
  imageUrl?: string;
}

const GameDisplay: React.FC<GameDisplayProps> = ({ gameState, imageUrl }) => {
  const gameTitle =
    ((gameState as Record<string, unknown>).game_title as string) ||
    ((gameState as Record<string, unknown>).gameTitle as string) ||
    "Fire Emblem GBA";

  return (
    <div className="game-display">
      <div className="game-screen">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt="Game Screen"
            className="game-image"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="placeholder-screen">
            <p>Waiting for game screen...</p>
            <p className="sub-text">{gameTitle}</p>
          </div>
        )}
      </div>

      <div className="objective-bar">
        <h3>Chapter Objective</h3>
        <p>{gameState.objective || "Defeat all enemies"}</p>
      </div>

      <div className="goals-section">
        <h3>AI Goals</h3>
        <div className="goals-container">
          <div className="goal-item">
            <span className="goal-label">Primary:</span>
            <span className="goal-text">
              {gameState.primaryGoal || "Awaiting objective..."}
            </span>
          </div>
          <div className="goal-item">
            <span className="goal-label">Secondary:</span>
            <span className="goal-text">
              {gameState.secondaryGoal || "None"}
            </span>
          </div>
          <div className="goal-item">
            <span className="goal-label">Tertiary:</span>
            <span className="goal-text">
              {gameState.tertiaryGoal || "None"}
            </span>
          </div>
        </div>
      </div>

      {gameState.otherNotes && (
        <div className="notes-section">
          <h4>Notes</h4>
          <p>{gameState.otherNotes}</p>
        </div>
      )}
    </div>
  );
};

export default GameDisplay;

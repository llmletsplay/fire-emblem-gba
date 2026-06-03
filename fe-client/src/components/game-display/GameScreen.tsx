import type { GameScreenProps } from "../../types/display";
import "./GameScreen.css";

export function GameScreen({ screenshotUrl }: GameScreenProps) {
  return (
    <div className="game-screen">
      <div className="game-screen__frame">
        {screenshotUrl ? (
          <img
            src={screenshotUrl}
            alt="Game Stream"
            className="game-screen__img"
          />
        ) : (
          <div className="game-screen__placeholder">
            <span>Waiting for stream...</span>
          </div>
        )}
      </div>
    </div>
  );
}

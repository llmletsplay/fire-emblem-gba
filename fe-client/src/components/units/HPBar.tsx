import type { HPBarProps } from "../../types/display";
import { getHPStatus } from "../../utils/transformers";
import "./HPBar.css";

export function HPBar({
  current,
  max,
  showNumbers = false,
  size = "md",
}: HPBarProps) {
  const percent = Math.max(0, Math.min(100, (current / max) * 100));
  const status = getHPStatus(current, max);

  return (
    <div className={`hp-bar hp-bar--${size}`}>
      <div className="hp-bar__track">
        <div
          className={`hp-bar__fill hp-bar__fill--${status}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      {showNumbers && (
        <span className="hp-bar__numbers">
          {current}/{max}
        </span>
      )}
    </div>
  );
}

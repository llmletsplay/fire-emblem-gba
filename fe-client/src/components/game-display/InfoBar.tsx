import type { InfoBarProps } from "../../types/display";
import { getChapterDisplayName } from "../../utils/chapterData";
import "./InfoBar.css";

export function InfoBar({
  chapterNumber,
  chapterTitle,
  turnNumber,
  phase,
  objective,
}: InfoBarProps) {
  const phaseClass = phase.toLowerCase() as "player" | "enemy" | "ally";
  const chapterDisplay = getChapterDisplayName(chapterNumber);

  return (
    <div className="info-bar">
      <div className="info-bar__left">
        <span className="info-bar__chapter-num">{chapterDisplay}</span>
        <span className="info-bar__chapter-title">{chapterTitle}</span>
        <span className="info-bar__divider">|</span>
        <span className={`info-bar__phase info-bar__phase--${phaseClass}`}>
          Turn {turnNumber} » {phase}
        </span>
      </div>

      <div className="info-bar__right">
        <span className="info-bar__objective-label">Objective:</span>
        <span className="info-bar__objective-text">{objective}</span>
      </div>
    </div>
  );
}

import type { ThoughtEntry as ThoughtEntryType } from "../../types/display";
import { formatTimestamp } from "../../utils/transformers";
import { ActionBadges } from "./ActionBadges";
import ReactMarkdown from "react-markdown";
import "./ThoughtEntry.css";

interface ThoughtEntryProps {
  entry: ThoughtEntryType;
  isNew?: boolean;
}

function parseThinkTags(text: string): {
  thinking: string | null;
  content: string;
} {
  const thinkMatch = text.match(/<think>([\s\S]*?)<\/think>/i);
  if (thinkMatch) {
    const thinking = thinkMatch[1].trim();
    const content = text.replace(/<think>[\s\S]*?<\/think>/gi, "").trim();
    return { thinking, content };
  }
  return { thinking: null, content: text };
}

function truncateText(text: string, maxLength: number = 300): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

export function ThoughtEntry({ entry, isNew }: ThoughtEntryProps) {
  const { thinking, content } = parseThinkTags(entry.text);
  const hasStructuredSections =
    entry.sections?.observation ||
    entry.sections?.reasoning ||
    entry.sections?.action;

  return (
    <div className={`thought-entry${isNew ? " thought-entry--new" : ""}`}>
      <div className="thought-entry__header">
        <span className="thought-entry__timestamp">
          {formatTimestamp(entry.timestamp)}
        </span>
        {entry.screenshot && (
          <img
            src={entry.screenshot}
            alt="Context"
            className="thought-entry__thumbnail"
            loading="lazy"
          />
        )}
      </div>

      {thinking && <p className="thought-entry__thinking">{thinking}</p>}

      {hasStructuredSections ? (
        <div className="thought-entry__sections">
          {entry.sections?.observation && (
            <div className="thought-entry__section thought-entry__section--observation">
              <div className="thought-entry__section-header">
                <span className="thought-entry__section-icon">👁</span>
                <span className="thought-entry__section-label">
                  Observation
                </span>
              </div>
              <div className="thought-entry__section-content">
                <ReactMarkdown>
                  {truncateText(entry.sections.observation)}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {entry.sections?.reasoning && (
            <div className="thought-entry__section thought-entry__section--reasoning">
              <div className="thought-entry__section-header">
                <span className="thought-entry__section-icon">💭</span>
                <span className="thought-entry__section-label">Reasoning</span>
              </div>
              <div className="thought-entry__section-content">
                <ReactMarkdown>
                  {truncateText(entry.sections.reasoning)}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {entry.actionButtons && entry.actionButtons.length > 0 && (
            <div className="thought-entry__section thought-entry__section--action">
              <div className="thought-entry__section-header">
                <span className="thought-entry__section-icon">🎮</span>
                <span className="thought-entry__section-label">Action</span>
              </div>
              <div className="thought-entry__action-sequence">
                {entry.actionButtons.map((btn, idx) => (
                  <span key={idx} className="thought-entry__action-btn">
                    {btn}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        content && (
          <div className="thought-entry__text">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )
      )}

      <ActionBadges buttons={entry.buttons} tools={entry.tools} />
    </div>
  );
}

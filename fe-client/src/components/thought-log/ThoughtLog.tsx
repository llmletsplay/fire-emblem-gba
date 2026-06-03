import { useEffect, useState } from "react";
import type { ThoughtLogProps } from "../../types/display";
import { ThoughtEntry } from "./ThoughtEntry";
import "./ThoughtLog.css";

const KEYART_IMAGES = ["/keyart/eirika.png", "/keyart/lute.png"];
const ROTATION_INTERVAL = 15000;

export function ThoughtLog({
  entries,
  isProcessing,
  memoryWrite,
}: ThoughtLogProps) {
  const [currentKeyart, setCurrentKeyart] = useState(0);
  const [persistedMemory, setPersistedMemory] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentKeyart((prev) => (prev + 1) % KEYART_IMAGES.length);
    }, ROTATION_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  // Persist memory - update when new memory arrives, keep visible until replaced
  useEffect(() => {
    if (memoryWrite) {
      setPersistedMemory(memoryWrite);
    }
  }, [memoryWrite]);

  // Get the latest entry (newest at end of array)
  const latestEntry = entries.length > 0 ? entries[entries.length - 1] : null;

  // Get recent actions from last 5 entries
  const recentActions = entries.slice(-5).map((e) => ({
    id: e.id,
    actions: e.actionButtons || [],
  }));

  return (
    <div className="thought-log-container">
      <div
        key={currentKeyart}
        className="thought-log__keyart"
        style={{ backgroundImage: `url(${KEYART_IMAGES[currentKeyart]})` }}
      />
      <div className="thought-log">
        {/* Current AI Thought - Single, Centered */}
        <div className="thought-log__current">
          {latestEntry ? (
            <ThoughtEntry key={latestEntry.id} entry={latestEntry} isNew />
          ) : (
            !isProcessing && (
              <div className="thought-log__empty">
                Waiting for AI activity...
              </div>
            )
          )}

          {isProcessing && (
            <div className="thought-log__thinking">
              <span className="thought-log__thinking-text">
                {"Thinking...".split("").map((char, i) => (
                  <span
                    key={i}
                    className="thought-log__thinking-char"
                    style={{ animationDelay: `${i * 0.12}s` }}
                  >
                    {char}
                  </span>
                ))}
              </span>
            </div>
          )}
        </div>

        {/* Footer: Recent Actions + Memory */}
        <div className="thought-log__footer">
          {/* Recent Actions */}
          {recentActions.some((r) => r.actions.length > 0) && (
            <div className="thought-log__actions-section">
              <span className="thought-log__section-label">RECENT ACTIONS</span>
              <div className="thought-log__action-list">
                {recentActions
                  .filter((r) => r.actions.length > 0)
                  .map((r) => (
                    <div key={r.id} className="thought-log__action-row">
                      {r.actions.map((btn, idx) => (
                        <span key={idx} className="thought-log__action-btn">
                          {btn}
                        </span>
                      ))}
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Latest Memory - Persistent */}
          <div className="thought-log__memory-section">
            <span className="thought-log__section-label">LATEST MEMORY</span>
            <p className="thought-log__memory-text">
              {persistedMemory || "No memories recorded yet"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

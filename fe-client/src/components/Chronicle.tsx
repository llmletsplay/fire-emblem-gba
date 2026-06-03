import React, { useEffect, useState } from "react";
import "../App.css";

interface ChronicleEntry {
  id: string;
  timestamp: string;
  interpretation: string;
  phase: string;
  actions: string[];
  chapter?: string;
  screenshot?: string;
  screenshot_url?: string;
}

interface ChronicleProps {
  ws: WebSocket | null;
}

const Chronicle: React.FC<ChronicleProps> = ({ ws }) => {
  const [entries, setEntries] = useState<ChronicleEntry[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<ChronicleEntry | null>(
    null,
  );
  const [loading] = useState(false);

  useEffect(() => {
    if (!ws) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        // Load initial chronicle entries
        if (data.chronicle_entries) {
          setEntries(data.chronicle_entries);
          // Use functional update to avoid stale closure
          setSelectedEntry((prev) => {
            if (!prev && data.chronicle_entries.length > 0) {
              return data.chronicle_entries[data.chronicle_entries.length - 1];
            }
            return prev;
          });
        }

        // Add new chronicle update
        if (data.chronicle_update) {
          setEntries((prev) => {
            const updated = [...prev, data.chronicle_update];
            return updated.slice(-100);
          });
          setSelectedEntry(data.chronicle_update);
        }
      } catch {
        // Silently ignore malformed messages
      }
    };

    ws.addEventListener("message", handleMessage);
    return () => {
      ws.removeEventListener("message", handleMessage);
    };
  }, [ws]);

  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const getPhaseColor = (phase: string): string => {
    switch (phase.toLowerCase()) {
      case "story_dialogue":
        return "#4CAF50";
      case "tactical_map":
        return "#FF9800";
      case "menu":
        return "#2196F3";
      case "transition":
        return "#9E9E9E";
      default:
        return "#757575";
    }
  };

  if (loading) {
    return (
      <div className="chronicle-container">
        <h2>Chronicle</h2>
        <div className="loading">Loading chronicle...</div>
      </div>
    );
  }

  return (
    <div className="chronicle-container">
      <h2>Chronicle</h2>

      <div className="chronicle-layout">
        {/* Entry List */}
        <div className="chronicle-list">
          <h3>Story Log ({entries.length} entries)</h3>
          <div className="chronicle-entries">
            {entries
              .slice()
              .reverse()
              .map((entry) => (
                <div
                  key={entry.id}
                  className={`chronicle-entry ${selectedEntry?.id === entry.id ? "selected" : ""}`}
                  onClick={() => setSelectedEntry(entry)}
                >
                  <div className="entry-header">
                    <span className="entry-time">
                      {formatTimestamp(entry.timestamp)}
                    </span>
                    <span
                      className="entry-phase"
                      style={{ backgroundColor: getPhaseColor(entry.phase) }}
                    >
                      {entry.phase.replace("_", " ")}
                    </span>
                  </div>
                  <div className="entry-preview">
                    {entry.interpretation.slice(0, 100)}...
                  </div>
                  {entry.chapter && (
                    <div className="entry-chapter">
                      Chapter: {entry.chapter}
                    </div>
                  )}
                </div>
              ))}
          </div>
        </div>

        {/* Selected Entry Details */}
        {selectedEntry && (
          <div className="chronicle-detail">
            <h3>Entry Details</h3>

            {selectedEntry.screenshot_url && (
              <div className="chronicle-screenshot">
                <img
                  src={selectedEntry.screenshot_url}
                  alt="Game screenshot"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
              </div>
            )}

            <div className="detail-section">
              <h4>Vision Interpretation</h4>
              <p className="interpretation-text">
                {selectedEntry.interpretation}
              </p>
            </div>

            <div className="detail-section">
              <h4>Game Phase</h4>
              <span
                className="phase-badge"
                style={{ backgroundColor: getPhaseColor(selectedEntry.phase) }}
              >
                {selectedEntry.phase.replace("_", " ").toUpperCase()}
              </span>
            </div>

            {selectedEntry.chapter && (
              <div className="detail-section">
                <h4>Chapter</h4>
                <p>{selectedEntry.chapter}</p>
              </div>
            )}

            {selectedEntry.actions && selectedEntry.actions.length > 0 && (
              <div className="detail-section">
                <h4>Actions Taken</h4>
                <div className="actions-list">
                  {selectedEntry.actions.map((action, index) => (
                    <span key={index} className="action-item">
                      {action}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="detail-section">
              <h4>Timestamp</h4>
              <p>{new Date(selectedEntry.timestamp).toLocaleString()}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Chronicle;

import { useState } from "react";
import "../styles/Data.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8787";

interface ExportLink {
  name: string;
  href: string;
  filename: string;
  description: string;
}

interface SpriteDownload {
  name: string;
  href: string;
  filename: string;
  description: string;
  count: number;
}

function Data() {
  const [runId, setRunId] = useState("");

  const q = runId ? `?run=${encodeURIComponent(runId)}` : "";

  const spriteDownloads: SpriteDownload[] = [
    {
      name: "Character Portraits",
      href: "/downloads/fe8-portraits.zip",
      filename: "fe8-portraits.zip",
      description: "All playable character and boss portraits (96x80 PNG)",
      count: 57,
    },
    {
      name: "Class Sprites",
      href: "/downloads/fe8-class-sprites.zip",
      filename: "fe8-class-sprites.zip",
      description: "Animated map sprites for all unit classes (GIF)",
      count: 50,
    },
    {
      name: "Map Images",
      href: "/downloads/fe8-map-sprites.zip",
      filename: "fe8-map-sprites.zip",
      description: "Chapter map overview images (PNG)",
      count: 24,
    },
    {
      name: "Logos & Box Art",
      href: "/downloads/fe8-logos.zip",
      filename: "fe8-logos.zip",
      description: "Official logos (EN/JP) and box art images",
      count: 4,
    },
  ];

  const links: ExportLink[] = [
    {
      name: "Run Data (ZIP)",
      href: `${API_BASE}/export.zip${q}`,
      filename: "export.zip",
      description: "Benchmarks, requests, snapshots, and sessions as CSV",
    },
    {
      name: "Raw JSONL Logs",
      href: `${API_BASE}/export_jsonl.zip${q}`,
      filename: "export_jsonl.zip",
      description: "Raw JSONL log files for detailed analysis",
    },
  ];

  const copyCurl = async (href: string, filename: string) => {
    const cmd = `curl -L ${JSON.stringify(href)} -o ${JSON.stringify(filename)}`;
    try {
      await navigator.clipboard.writeText(cmd);
      alert("Copied curl command to clipboard!");
    } catch (e) {
      console.error("Failed to copy", e);
    }
  };

  return (
    <div className="data-page">
      <h1>Download Data</h1>
      <p className="data-intro">
        Download FE8-specific game assets and run data from Fire Emblem GBA AI
        sessions.
      </p>

      <section className="sprites-section">
        <h2>Game Assets</h2>
        <p className="section-desc">
          Fire Emblem: The Sacred Stones sprites, portraits, and artwork. These
          bundles are FE8-specific.
        </p>
        <div className="sprite-grid">
          {spriteDownloads.map((sprite) => (
            <div key={sprite.name} className="sprite-card">
              <div className="sprite-header">
                <h3>{sprite.name}</h3>
                <span className="sprite-count">{sprite.count} files</span>
              </div>
              <p>{sprite.description}</p>
              <a
                href={sprite.href}
                download={sprite.filename}
                className="btn btn-primary"
              >
                Download ZIP
              </a>
            </div>
          ))}
        </div>
      </section>

      <section className="experiment-section">
        <h2>Run Data</h2>
        <p className="section-desc">
          Benchmarks, LLM request logs, and session data from agent runs.
        </p>

        <div className="run-filter">
          <label htmlFor="runId">Filter by Run ID:</label>
          <input
            type="text"
            id="runId"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
          placeholder="e.g., run-gpt-4o-001"
          />
          {runId && <span className="filter-active">Filtering: {runId}</span>}
        </div>

        <div className="export-grid">
          {links.map((link) => (
            <div key={link.name} className="export-card">
              <h3>{link.name}</h3>
              <p>{link.description}</p>
              <div className="export-actions">
                <a
                  href={link.href}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-primary"
                >
                  Download
                </a>
                <button
                  className="btn btn-secondary"
                  onClick={() => copyCurl(link.href, link.filename)}
                >
                  Copy curl
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="fair-use-section">
        <h2>Fair Use Notice</h2>
        <p>
          Fire Emblem: The Sacred Stones is a trademark of Nintendo and
          Intelligent Systems. Fire Emblem: The Blazing Blade is also a
          trademark of its respective rights holders. All game assets,
          screenshots, and artwork displayed on this site are the property of
          their respective copyright holders.
        </p>
        <p>
          The use of these materials is believed to constitute "Fair Use" under
          applicable copyright law given that:
        </p>
        <ul>
          <li>
            This project is used in a non-commercial, educational, and research
            setting
          </li>
          <li>
            The use does not significantly impede the right of the copyright
            holder to sell the copyrighted material
          </li>
          <li>
            Materials are used in a largely unaltered state for identification
            and reference purposes
          </li>
          <li>
            This project serves to demonstrate AI capabilities and does not
            compete with or substitute for the original work
          </li>
        </ul>
        <p className="disclaimer-note">
          This is an independent research project exploring AI gameplay. It is
          not affiliated with, endorsed by, or connected to Nintendo,
          Intelligent Systems, or any related entities. If you are a rights
          holder and have concerns, please contact us.
        </p>
      </section>
    </div>
  );
}

export default Data;

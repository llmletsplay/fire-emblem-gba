import { useState, useEffect, useCallback } from "react";
import "../styles/Benchmarks.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8787";

interface BenchmarkData {
  chapters: ChapterSummary[];
  overall: OverallStats;
}

interface ChapterSummary {
  chapter: number;
  duration_sec: number;
  loops: number;
  tokens_used: number;
  run_id: string;
}

interface OverallStats {
  total_chapters: number;
  total_duration_sec: number;
  total_tokens: number;
  avg_chapter_duration: number;
  avg_tokens_per_chapter: number;
}

function Benchmarks() {
  const [data, setData] = useState<BenchmarkData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState("");

  const fetchBenchmarks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const q = runId ? `?run=${encodeURIComponent(runId)}` : "";
      const res = await fetch(`${API_BASE}/benchmarks${q}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch benchmarks");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchBenchmarks();
  }, [fetchBenchmarks]);

  const formatDuration = (sec: number) => {
    if (sec < 60) return `${sec.toFixed(1)}s`;
    const min = Math.floor(sec / 60);
    const s = sec % 60;
    return `${min}m ${s.toFixed(0)}s`;
  };

  return (
    <div className="benchmarks-page">
      <h1>Benchmarks</h1>
      <p className="benchmarks-intro">
        Performance metrics from Fire Emblem AI gameplay sessions. Data updates
        in real-time when the backend is running.
      </p>

      <section className="run-filter">
        <label htmlFor="runId">Filter by Run ID:</label>
        <input
          type="text"
          id="runId"
          value={runId}
          onChange={(e) => setRunId(e.target.value)}
          placeholder="Leave empty for all runs"
        />
        <button className="btn btn-secondary" onClick={fetchBenchmarks}>
          Refresh
        </button>
      </section>

      {loading && <div className="loading">Loading benchmarks...</div>}

      {error && (
        <div className="error">
          <p>Failed to load benchmarks: {error}</p>
          <p className="error-hint">
            Make sure the backend is running with{" "}
            <code>FE_BENCH_HTTP_ENABLED=true</code>
          </p>
        </div>
      )}

      {data && (
        <>
          <section className="overall-stats">
            <h2>Overall Statistics</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{data.overall.total_chapters}</div>
                <div className="stat-label">Chapters</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {formatDuration(data.overall.total_duration_sec)}
                </div>
                <div className="stat-label">Total Time</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {data.overall.total_tokens.toLocaleString()}
                </div>
                <div className="stat-label">Total Tokens</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {formatDuration(data.overall.avg_chapter_duration)}
                </div>
                <div className="stat-label">Avg Chapter Time</div>
              </div>
            </div>
          </section>

          <section className="chapter-table">
            <h2>Per-Chapter Breakdown</h2>
            {data.chapters.length === 0 ? (
              <p>No chapter data available.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Chapter</th>
                    <th>Duration</th>
                    <th>Loops</th>
                    <th>Tokens</th>
                    <th>Run ID</th>
                  </tr>
                </thead>
                <tbody>
                  {data.chapters.map((ch, i) => (
                    <tr key={i}>
                      <td>{ch.chapter}</td>
                      <td>{formatDuration(ch.duration_sec)}</td>
                      <td>{ch.loops}</td>
                      <td>{ch.tokens_used.toLocaleString()}</td>
                      <td className="run-id">{ch.run_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default Benchmarks;

import "../styles/Docs.css";

function Docs() {
  return (
    <div className="docs">
      <h1>Documentation</h1>
      <p className="docs-intro">
        Technical overview of the Fire Emblem GBA agent harness, including
        FE7/FE8 memory support, command execution, and runtime limitations.
      </p>

      <nav className="docs-nav">
        <a href="#architecture">Architecture</a>
        <a href="#memory-reading">Memory Reading</a>
        <a href="#data-available">Data Available</a>
        <a href="#limitations">Limitations</a>
        <a href="#setup">Setup Guide</a>
      </nav>

      <section id="architecture" className="docs-section">
        <h2>System Architecture</h2>
        <div className="arch-diagram">
          <div className="arch-flow">
            <div className="arch-box">mGBA + FE7/FE8 ROM</div>
            <div className="arch-arrow">Lua TCP socket</div>
            <div className="arch-box">Python Memory Reader</div>
            <div className="arch-arrow">LLM + Command Executor</div>
            <div className="arch-box">React Overlay</div>
          </div>
        </div>
        <div className="arch-details">
          <div className="detail-card">
            <h3>mGBA Lua Bridge</h3>
            <p>
              Captures screenshots, queues controller input, reads ROM headers,
              and exposes raw memory ranges through a local socket.
            </p>
          </div>
          <div className="detail-card">
            <h3>GBA Memory Reader</h3>
            <p>
              Selects FE7 or FE8 addresses from the game registry and parses
              unit arrays, phase, turn, cursor, terrain, and UI state.
            </p>
          </div>
          <div className="detail-card">
            <h3>LLM Runtime</h3>
            <p>
              Combines memory JSON, screenshots, session memory, and prompts to
              request semantic tactical commands from a model.
            </p>
          </div>
          <div className="detail-card">
            <h3>Command Executor</h3>
            <p>
              Parses and validates `COMMAND:` output, then converts it to
              deterministic GBA button sequences.
            </p>
          </div>
        </div>
      </section>

      <section id="memory-reading" className="docs-section">
        <h2>Memory Reading</h2>
        <p>
          The harness supports Fire Emblem 7 (`AE7E`) and Fire Emblem 8
          (`BE8E`). The shared reader uses per-game registry metadata so the
          same runtime can read both games.
        </p>

        <h3>Core Addresses</h3>
        <table className="docs-table">
          <thead>
            <tr>
              <th>Data</th>
              <th>FE7</th>
              <th>FE8</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Phase</td>
              <td>
                <code>0x0202BC07</code>
              </td>
              <td>
                <code>0x0202BCF9</code>
              </td>
            </tr>
            <tr>
              <td>Chapter</td>
              <td>
                <code>0x0202BC06</code>
              </td>
              <td>
                <code>0x0202BCFE</code>
              </td>
            </tr>
            <tr>
              <td>Turn</td>
              <td>
                <code>0x0202BC08</code>
              </td>
              <td>
                <code>0x0202BD00</code>
              </td>
            </tr>
            <tr>
              <td>Player units</td>
              <td>
                <code>0x0202BD08</code>
              </td>
              <td>
                <code>0x0202BE4C</code>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section id="data-available" className="docs-section">
        <h2>Data Currently Available</h2>
        <div className="status-grid">
          <div className="status-card status-available">
            <h3>Implemented</h3>
            <ul>
              <li>ROM detection and FE7/FE8 registry selection</li>
              <li>Chapter, turn, phase, cursor, and display cursor</li>
              <li>Player, enemy, and NPC unit arrays</li>
              <li>HP, stats, level, class, position, items, and weapon ranks</li>
              <li>Moved/rescued/alive status per unit</li>
              <li>Chapter objectives and boss/seize metadata where known</li>
              <li>FE7 tutorial guidance and FE8 event-slot tutorial targets</li>
            </ul>
          </div>

          <div className="status-card status-partial">
            <h3>Partial</h3>
            <ul>
              <li>Terrain and map dimensions</li>
              <li>Movement tiles and attack opportunities</li>
              <li>Dialogue and menu detection</li>
              <li>Vision-derived overlay/tile cues</li>
            </ul>
          </div>

          <div className="status-card status-unavailable">
            <h3>Not Yet Exposed</h3>
            <ul>
              <li>Battle forecast hit, damage, and crit</li>
              <li>Full danger-zone computation</li>
              <li>Convoy and shop inventories</li>
              <li>Fog of war state</li>
              <li>Support point internals</li>
            </ul>
          </div>
        </div>
      </section>

      <section id="limitations" className="docs-section">
        <h2>Known Limitations</h2>
        <div className="limitation-list">
          <div className="limitation">
            <h3>US ROM Builds</h3>
            <p>
              Address maps are verified against the US FE7 and FE8 ROM codes.
              Other regional builds may use different layouts.
            </p>
          </div>
          <div className="limitation">
            <h3>Memory Beats Vision</h3>
            <p>
              Screenshot-derived fields are useful for text boxes and overlays,
              but memory-derived state should win when the two disagree.
            </p>
          </div>
          <div className="limitation">
            <h3>Battle Forecast Gap</h3>
            <p>
              Forecast data is still a priority improvement because it would let
              the agent evaluate attacks before committing.
            </p>
          </div>
        </div>
      </section>

      <section id="setup" className="docs-section">
        <h2>Setup Guide</h2>
        <ol>
          <li>Install Python 3.10+, Node.js 18+, and mGBA with Lua scripting.</li>
          <li>Copy `.env.example` to `.env`.</li>
          <li>Place a legally obtained FE7 or FE8 ROM in `roms/`.</li>
          <li>
            Set `FE_GAME` and `ROM_FILE`, for example `FE_GAME=fe7` and
            `ROM_FILE=FE7.gba`.
          </li>
          <li>Set `LLM_PROVIDER` and the required API key or local endpoint.</li>
          <li>Run `npm start` from the repository root.</li>
        </ol>
      </section>
    </div>
  );
}

export default Docs;

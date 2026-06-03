import { Link } from "react-router-dom";
import "../styles/Home.css";

function Home() {
  return (
    <div className="home">
      {/* Background character art */}
      <div className="hero-bg">
        <img src="/keyart/eirika.png" alt="" className="bg-char bg-char-left" />
        <img src="/keyart/lute.png" alt="" className="bg-char bg-char-right" />
      </div>

      <section className="hero">
        <img
          src="/logos/logo_en.png"
          alt="Fire Emblem"
          className="hero-logo"
        />
        <h1>Fire Emblem GBA AI</h1>
        <p className="hero-subtitle">
          An LLM-powered agent harness for Fire Emblem 7 and Fire Emblem 8
        </p>
        <div className="hero-actions">
          <Link to="/about" className="btn btn-primary">
            Learn More
          </Link>
          <a
            href="https://github.com/llmletsplay/fire-emblem-gba"
            target="_blank"
            rel="noreferrer"
            className="btn btn-secondary"
          >
            View on GitHub
          </a>
        </div>
      </section>

      <section className="features">
        <h2>How It Works</h2>
        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon">1</div>
            <h3>Screen Capture</h3>
            <p>
              The AI captures screenshots from the mGBA emulator in real-time
              using Lua scripting.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">2</div>
            <h3>Vision Analysis</h3>
            <p>
              A vision model analyzes the game screen to understand the current
              battlefield state.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">3</div>
            <h3>LLM Decision</h3>
            <p>
              An LLM (GPT-4, Claude, etc.) makes tactical decisions based on the
              memory-backed game state.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">4</div>
            <h3>Action Execution</h3>
            <p>
              Button inputs are sent back to the emulator to execute the AI's
              decisions.
            </p>
          </div>
        </div>
      </section>

      <section className="stats-preview">
        <h2>Project Data</h2>
        <p>
          Explore benchmarks, session data, and downloadable FE8 asset bundles.
        </p>
        <div className="stats-actions">
          <Link to="/benchmarks" className="btn btn-outline">
            View Benchmarks
          </Link>
          <Link to="/data" className="btn btn-outline">
            Download Data
          </Link>
        </div>
      </section>
    </div>
  );
}

export default Home;

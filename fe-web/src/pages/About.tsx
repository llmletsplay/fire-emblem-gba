import "../styles/About.css";

function About() {
  return (
    <div className="about">
      <h1>About Fire Emblem GBA AI</h1>

      {/* Fire Emblem Symbol Animation */}
      <div className="fe-symbol-container">
        <svg
          className="fe-symbol"
          viewBox="0 0 100 100"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Shield outline */}
          <path d="M50 5 L90 20 L90 55 Q90 80 50 95 Q10 80 10 55 L10 20 Z" />
          {/* Inner shield */}
          <path d="M50 15 L80 27 L80 52 Q80 72 50 85 Q20 72 20 52 L20 27 Z" />
          {/* Sword */}
          <path d="M50 25 L50 75" />
          <path d="M40 35 L60 35" />
          <path d="M45 30 L55 30 L55 40 L45 40 Z" />
          {/* Decorative elements */}
          <path d="M30 45 Q40 50 50 45 Q60 50 70 45" />
          <path d="M35 60 L50 55 L65 60" />
        </svg>
      </div>

      <section className="about-section">
        <h2>Project Overview</h2>
        <p>
          Fire Emblem AI is an open-source research project that explores
          whether large language models can successfully play tactical RPGs. The
          system reads live GBA Fire Emblem memory, uses screenshots and LLM
          reasoning, and executes tactical decisions in FE7 and FE8.
        </p>
      </section>

      <section className="about-section">
        <h2>Architecture</h2>
        <div className="architecture">
          <div className="arch-component">
            <h3>Emulator Interface</h3>
            <p>
              mGBA emulator with Lua scripting provides screen capture and input
              control via sockets.
            </p>
          </div>
          <div className="arch-component">
            <h3>Game State Parser</h3>
            <p>
              Reads FE7/FE8 memory addresses to extract unit positions, HP,
              stats, phase, cursor, and objectives.
            </p>
          </div>
          <div className="arch-component">
            <h3>Vision Model</h3>
            <p>
              Processes screenshots to describe the current game state in
              natural language.
            </p>
          </div>
          <div className="arch-component">
            <h3>LLM Decision Engine</h3>
            <p>
              Uses tactical prompts and semantic commands for unit movement and
              combat.
            </p>
          </div>
          <div className="arch-component">
            <h3>WebSocket Server</h3>
            <p>
              Streams real-time game state and AI decisions to the streaming
              overlay.
            </p>
          </div>
          <div className="arch-component">
            <h3>Chronicle System</h3>
            <p>
              Records story interpretations and screenshots for narrative
              tracking.
            </p>
          </div>
        </div>
      </section>

      <section className="about-section">
        <h2>Supported LLM Providers</h2>
        <ul className="provider-list">
          <li>
            <strong>OpenAI</strong> - GPT-4, GPT-4o
          </li>
          <li>
            <strong>Anthropic</strong> - Claude Sonnet, Claude Opus
          </li>
          <li>
            <strong>Google</strong> - Gemini
          </li>
          <li>
            <strong>Local</strong> - Ollama, LMStudio
          </li>
          <li>
            <strong>Cloud</strong> - Groq, Together, Grok
          </li>
          <li>
            <strong>Custom</strong> - Any OpenAI-compatible endpoint
          </li>
          <li>
            <strong>Z.AI</strong> - GLM-compatible hosted model support
          </li>
        </ul>
      </section>

      <section className="about-section">
        <h2>Research Goals</h2>
        <ul>
          <li>Can LLMs understand and execute tactical gameplay?</li>
          <li>How do different models compare in strategic decision-making?</li>
          <li>What prompting strategies work best for game AI?</li>
          <li>Can AI complete a full playthrough of Fire Emblem?</li>
        </ul>
      </section>

      <section className="about-section">
        <h2>Open Source</h2>
        <p>
          This project is fully open source under the MIT license. Contributions
          are welcome!
        </p>
        <a
          href="https://github.com/llmletsplay/fire-emblem-gba"
          target="_blank"
          rel="noreferrer"
          className="btn btn-primary"
        >
          View on GitHub
        </a>
      </section>
    </div>
  );
}

export default About;

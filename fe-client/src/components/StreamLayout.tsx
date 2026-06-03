import React, { useState, useEffect, useRef } from "react";
import "./StreamLayout.css";
import type { GameState, LogEntry, ChronicleEntry } from "../types/gameTypes";

interface StreamLayoutProps {
  gameState: GameState;
  wsConnected: boolean;
  logs: LogEntry[];
  aiThoughts: string[];
  currentScreenshot: string;
  chronicle: ChronicleEntry[];
  visionDescription: string | null;
  visionProcessing: boolean;
  ws: WebSocket | null;
}

const UNIT_CYCLE_INTERVAL = 4000;

const CLASS_SPRITES: Record<string, string> = {
  lord: "Ma_gba_lord_eirika_playable.gif",
  "lord (eirika)": "Ma_gba_lord_eirika_playable.gif",
  "lord (ephraim)": "Ma_gba_lord_ephraim_playable.gif",
  "great lord": "Ma_gba_great_lord_eirika_playable.gif",
  "great lord (eirika)": "Ma_gba_great_lord_eirika_playable.gif",
  "great lord (ephraim)": "Ma_gba_great_lord_ephraim_playable.gif",
  cavalier: "Ma_gba_cavalier_playable.gif",
  paladin: "Ma_gba_paladin_playable.gif",
  "great knight": "Ma_gba_great_knight_playable.gif",
  troubadour: "Ma_gba_troubadour_playable.gif",
  valkyrie: "Ma_gba_valkyrie_playable.gif",
  ranger: "Ma_gba_ranger_playable.gif",
  "mage knight": "Ma_gba_mage_knight_playable.gif",
  myrmidon: "Ma_gba_myrmidon_playable.gif",
  swordmaster: "Ma_gba_swordmaster_playable.gif",
  mercenary: "Ma_gba_mercenary_playable.gif",
  hero: "Ma_gba_hero_playable.gif",
  thief: "Ma_gba_thief_playable.gif",
  rogue: "Ma_gba_rogue_playable.gif",
  assassin: "Ma_gba_assassin_playable.gif",
  fighter: "Ma_gba_fighter_playable.gif",
  warrior: "Ma_gba_warrior_playable.gif",
  berserker: "Ma_gba_berserker_playable.gif",
  journeyman: "Ma_gba_journeyman_playable.gif",
  pirate: "Ma_gba_berserker_playable.gif",
  knight: "Ma_gba_knight_playable.gif",
  general: "Ma_gba_general_playable.gif",
  archer: "Ma_gba_archer_female_playable.gif",
  sniper: "Ma_gba_sniper_playable.gif",
  "pegasus knight": "Ma_gba_pegasus_knight_playable.gif",
  falcoknight: "Ma_gba_falcoknight_playable.gif",
  "wyvern rider": "Ma_gba_wyvern_rider_playable.gif",
  "wyvern lord": "Ma_gba_wyvern_lord_playable.gif",
  "wyvern knight": "Ma_gba_wyvern_lord_playable.gif",
  mage: "Ma_gba_mage_playable.gif",
  sage: "Ma_gba_sage_playable.gif",
  pupil: "Ma_gba_mage_playable.gif",
  shaman: "Ma_gba_druid_playable.gif",
  druid: "Ma_gba_druid_playable.gif",
  summoner: "Ma_gba_summoner_playable.gif",
  cleric: "Ma_gba_cleric_playable.gif",
  priest: "Ma_gba_monk_playable.gif",
  monk: "Ma_gba_monk_playable.gif",
  bishop: "Ma_gba_bishop_playable.gif",
  dancer: "Ma_gba_dancer_tethys_playable.gif",
  manakete: "Ma_gba_manakete_myrrh_playable.gif",
  recruit: "Ma_gba_journeyman_playable.gif",
  soldier: "Ma_gba_soldier_enemy.gif",
  brigand: "Ma_gba_brigand_enemy.gif",
  revenant: "Ma_gba_revenant_enemy.gif",
  entombed: "Ma_gba_revenant_enemy.gif",
  bonewalker: "Ma_gba_soldier_enemy.gif",
  mogall: "Ma_gba_mogall_enemy.gif",
  "arch mogall": "Ma_gba_mogall_enemy.gif",
  gargoyle: "Ma_gba_gargoyle_enemy.gif",
  deathgoyle: "Ma_gba_gargoyle_enemy.gif",
  bael: "Ma_gba_bael_enemy.gif",
  "elder bael": "Ma_gba_bael_enemy.gif",
  "mauthe doog": "Ma_gba_mauthe_doog_enemy.gif",
  gwyllgi: "Ma_gba_mauthe_doog_enemy.gif",
  "draco zombie": "Ma_gba_draco_zombie_enemy.gif",
  "demon king": "Ma_gba_demon_king_enemy.gif",
};

const getClassSprite = (unitClass: string): string => {
  const normalized = unitClass.toLowerCase().trim();
  const sprite = CLASS_SPRITES[normalized];
  return sprite
    ? `/sprites/classes/${sprite}`
    : "/sprites/classes/Ma_gba_soldier_enemy.gif";
};

const getChapterMapPath = (chapterNum: number | string | undefined): string => {
  if (chapterNum === undefined || chapterNum === null)
    return "/sprites/maps/prologue.png";
  const num =
    typeof chapterNum === "string"
      ? chapterNum.toLowerCase()
      : String(chapterNum);
  const mapFiles: Record<string, string> = {
    "0": "prologue.png",
    prologue: "prologue.png",
    "1": "ch01.png",
    "2": "ch02.png",
    "3": "ch03.png",
    "4": "ch04.png",
    "5": "ch05.png",
    "5x": "ch05x.png",
    "6": "ch06.png",
    "7": "ch07.png",
    "8": "ch08.png",
    "9": "ch08.png",
    "9x": "ch09x.png",
    "10": "ch10-eirika.png",
    "11": "ch11-eirika.png",
    "11x": "ch11x-eirika.png",
    "12": "ch12-eirika.png",
    "12x": "ch12x-eirika.png",
    "13": "ch13-eirika.png",
    "13x": "ch13x-eirika.png",
    "14": "ch14-eirika.png",
    "14x": "ch14x-eirika.png",
    "15": "ch15.png",
    tower1: "tower-valni-1.png",
    tower2: "tower-valni-2.png",
    tower3: "tower-valni-3.png",
  };
  return `/sprites/maps/${mapFiles[num] || "prologue.png"}`;
};

interface AIActivity {
  id: number;
  timestamp: string;
  screenshot?: string;
  thinking?: string;
  commentary?: string;
  actions?: string[];
  tools?: string[];
}

const StreamLayout: React.FC<StreamLayoutProps> = ({
  gameState,
  wsConnected,
  logs,
  aiThoughts,
  currentScreenshot,
  visionProcessing,
}) => {
  const units = gameState.units || [];
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [aiActivity, setAiActivity] = useState<AIActivity[]>([]);
  const lastThoughtRef = useRef<string>("");

  useEffect(() => {
    if (units.length === 0) return;
    const interval = setInterval(() => {
      setHighlightedIndex((prev) => (prev + 1) % units.length);
    }, UNIT_CYCLE_INTERVAL);
    return () => clearInterval(interval);
  }, [units.length]);

  useEffect(() => {
    if (highlightedIndex >= units.length && units.length > 0) {
      setHighlightedIndex(0);
    }
  }, [units.length, highlightedIndex]);

  // Parse AI thoughts into structured activity
  useEffect(() => {
    if (aiThoughts.length > 0 && aiThoughts[0] !== lastThoughtRef.current) {
      lastThoughtRef.current = aiThoughts[0];
      const thought = aiThoughts[0];

      // Extract button inputs
      const actionPattern = /\b(UP|DOWN|LEFT|RIGHT|A|B|START|SELECT|L|R)\b/gi;
      const actionMatches = thought.match(actionPattern);
      const actions = actionMatches
        ? [...new Set(actionMatches.map((a) => a.toUpperCase()))]
        : [];

      // Extract tool usage
      const tools: string[] = [];
      const lowerThought = thought.toLowerCase();
      if (lowerThought.includes("move")) tools.push("move");
      if (lowerThought.includes("attack")) tools.push("attack");
      if (lowerThought.includes("wait")) tools.push("wait");
      if (lowerThought.includes("item")) tools.push("item");
      if (lowerThought.includes("heal")) tools.push("heal");
      if (lowerThought.includes("rescue")) tools.push("rescue");

      const newActivity: AIActivity = {
        id: Date.now(),
        timestamp: new Date().toLocaleTimeString(),
        screenshot: currentScreenshot || undefined,
        thinking: thought.replace(/^\[.*?\]\s*/, ""),
        actions: actions.length > 0 ? actions : undefined,
        tools: tools.length > 0 ? tools : undefined,
      };

      setAiActivity((prev) => [newActivity, ...prev].slice(0, 15));
    }
  }, [aiThoughts, currentScreenshot]);

  const chapterMapSrc = getChapterMapPath(gameState.chapter?.number);
  const gameTitle =
    ((gameState as Record<string, unknown>).game_title as string) ||
    ((gameState as Record<string, unknown>).gameTitle as string) ||
    "Fire Emblem GBA";

  return (
    <div className="stream-container">
      <header className="stream-header">
        <div className="header-left">
          <img
            src="/branding/fe-sacred-stones-logo.png"
            alt="Fire Emblem"
            className="header-logo"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
          <div className="title-block">
            <h1>{gameTitle}</h1>
            <div className="subtitle">
              <span className="chapter-badge">
                Ch. {gameState.chapter?.number ?? "??"}
              </span>
              <span className="turn-badge">
                Turn {gameState.turn ?? gameState.turnNumber ?? 0}
              </span>
              <span
                className={`phase-badge ${(gameState.phase || "player").toLowerCase()}`}
              >
                {gameState.phase || "Player"} Phase
              </span>
            </div>
          </div>
        </div>
        <div className="header-center">
          <div className="status-row">
            <span
              className={`connection-dot ${wsConnected ? "connected" : ""}`}
            />
            <span className="meta-tag">
              {((gameState as Record<string, unknown>)
                .providerName as string) || "AI"}
            </span>
            <span className="meta-divider">/</span>
            <span className="meta-tag">{gameState.modelName || "Vision"}</span>
          </div>
        </div>
        <div className="header-right">
          <div className="unit-counts">
            <div className="count-box ally">
              <span className="count-num">{gameState.allyCount || 0}</span>
              <span className="count-label">Allies</span>
            </div>
            <div className="count-box enemy">
              <span className="count-num">{gameState.enemyCount || 0}</span>
              <span className="count-label">Enemies</span>
            </div>
          </div>
        </div>
      </header>

      <div className="stream-body">
        {/* Left Panel - Map & Units */}
        <aside className="panel-left">
          <div className="chapter-map-section">
            <div className="panel-header">
              <h2>Chapter Map</h2>
            </div>
            <div className="chapter-map-container">
              <img
                src={chapterMapSrc}
                alt="Chapter Map"
                className="chapter-map-img"
              />
            </div>
          </div>
          <div className="units-section">
            <div className="panel-header">
              <h2>Units</h2>
              <span className="unit-count">{units.length}</span>
            </div>
            <div className="units-list">
              {units.slice(0, 8).map((unit, index) => (
                <div
                  key={unit.id}
                  className={`unit-row ${index === highlightedIndex ? "highlighted" : ""} ${
                    unit.affiliation === "enemy"
                      ? "enemy"
                      : unit.affiliation === "ally"
                        ? "ally"
                        : "player"
                  }`}
                >
                  <img
                    src={getClassSprite(unit.unitClass)}
                    alt={unit.unitClass}
                    className="unit-sprite"
                  />
                  <div className="unit-content">
                    <div className="unit-info">
                      <span className="unit-name">{unit.name}</span>
                      <span className="unit-class">{unit.unitClass}</span>
                    </div>
                    <div className="unit-stats">
                      <div className="hp-mini">
                        <div
                          className="hp-fill"
                          style={{
                            width: `${(unit.hp / unit.maxHp) * 100}%`,
                            background:
                              unit.hp < unit.maxHp / 3
                                ? "linear-gradient(90deg, #ef4444, #dc2626)"
                                : unit.hp < unit.maxHp / 2
                                  ? "linear-gradient(90deg, #f59e0b, #d97706)"
                                  : "linear-gradient(90deg, #22c55e, #16a34a)",
                          }}
                        />
                      </div>
                      <span className="hp-nums">
                        {unit.hp}/{unit.maxHp}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Center - Single Game Display */}
        <main className="display-main">
          <section className="game-display-box single">
            <div className="display-label">
              <span className="label-dot live" />
              <span>Game Stream</span>
              {visionProcessing && (
                <span className="analyzing">AI Processing...</span>
              )}
            </div>
            <div className="gba-frame">
              {gameState.screenshotUrl ? (
                <img
                  src={gameState.screenshotUrl}
                  alt="Game"
                  className="gba-screen"
                />
              ) : (
                <div className="gba-placeholder">Waiting for stream...</div>
              )}
            </div>
          </section>

          <div className="objective-bar">
            <span className="obj-label">Objective:</span>
            <span className="obj-text">
              {gameState.chapter?.objective ||
                gameState.objective ||
                "Defeat all enemies"}
            </span>
          </div>
        </main>

        {/* Right Panel - Combined AI Activity */}
        <aside className="panel-right">
          <div className="panel-section ai-activity-section">
            <div className="panel-header">
              <h2>AI Activity</h2>
            </div>
            <div className="ai-activity-feed">
              {aiActivity.length > 0 ? (
                aiActivity.slice(0, 8).map((item) => (
                  <div key={item.id} className="ai-activity-item">
                    <div className="activity-header">
                      {item.screenshot && (
                        <img
                          src={item.screenshot}
                          alt="Context"
                          className="activity-thumbnail"
                        />
                      )}
                      <span className="activity-time">{item.timestamp}</span>
                    </div>

                    {item.thinking && (
                      <p className="activity-thinking">{item.thinking}</p>
                    )}

                    <div className="activity-badges">
                      {item.actions &&
                        item.actions.map((action, i) => (
                          <span key={i} className="action-badge">
                            {action}
                          </span>
                        ))}
                      {item.tools &&
                        item.tools.map((tool, i) => (
                          <span key={i} className="tool-badge">
                            {tool}
                          </span>
                        ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="empty-state">Waiting for AI...</div>
              )}
            </div>
          </div>

          <div className="panel-section log-section">
            <div className="panel-header">
              <h2>Game Log</h2>
            </div>
            <div className="log-feed">
              {logs.slice(0, 5).map((log) => (
                <div key={log.id} className={`log-item log-${log.type}`}>
                  <span className="log-msg">{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default StreamLayout;

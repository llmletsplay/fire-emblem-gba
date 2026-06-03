import { useState, useEffect, useMemo, useCallback } from "react";
import "./styles/base.css";
import { StreamOverlay } from "./components/layout/StreamOverlay";
import type { GameState, LogEntry, ChronicleEntry } from "./types/gameTypes";
import type {
  WsMessage,
  StateUpdatePayload,
  LogEntryPayload,
  VisionPayload,
  MemoryWritePayload,
} from "./types/ws";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8765";

const INITIAL_GAME_STATE: GameState = {
  phase: "Player",
  turnNumber: 0,
  units: [],
};

// Log types that should be shown in the action log (gameplay + AI only)
const GAMEPLAY_LOG_TYPES = ["movement", "combat", "action", "battle", "ai"];

// Type aliases for payload access
type StatePayload = StateUpdatePayload & {
  screenshotUrl?: string;
  chronicle_entries?: ChronicleEntry[];
  chronicle_update?: ChronicleEntry;
  session_id?: string;
};

const isKnownLogCategory = (value: string): value is LogEntry["type"] => {
  switch (value) {
    case "action":
    case "battle":
    case "system":
    case "error":
    case "ai":
    case "combat":
    case "movement":
    case "info":
      return true;
    default:
      return false;
  }
};

type AiThoughtMsg = { type: "ai_thought"; payload: { thought: string } };

function App() {
  const [gameState, setGameState] = useState<GameState>(INITIAL_GAME_STATE);
  const [wsConnected, setWsConnected] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [aiThoughts, setAiThoughts] = useState<string[]>([]);
  const [currentScreenshot, setCurrentScreenshot] = useState<string>("");
  const [chronicle, setChronicle] = useState<ChronicleEntry[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>("");
  const [showAllSessions, setShowAllSessions] = useState(false);
  const [visionState, setVisionState] = useState<{
    description: string | null;
    processing: boolean;
  }>({
    description: null,
    processing: false,
  });
  const [memoryWrite, setMemoryWrite] = useState<string | null>(null);
  const [aiProcessing, setAiProcessing] = useState<{
    status: "idle" | "thinking" | "complete" | "error";
    model?: string;
  }>({ status: "idle" });
  const [, setWs] = useState<WebSocket | null>(null);

  // Filter chronicle by session
  const filteredChronicle = useMemo(() => {
    if (showAllSessions || !currentSessionId) {
      return chronicle;
    }
    return chronicle.filter((entry) => entry.session_id === currentSessionId);
  }, [chronicle, currentSessionId, showAllSessions]);

  const addLog = useCallback(
    (
      message: string,
      type:
        | "action"
        | "battle"
        | "system"
        | "error"
        | "ai"
        | "combat"
        | "movement"
        | "info" = "info",
    ) => {
      // Filter out non-gameplay logs for cleaner streaming display
      if (!GAMEPLAY_LOG_TYPES.includes(type)) return;

      const newLog: LogEntry = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        message,
        type,
      };
      setLogs((prev) => [newLog, ...prev].slice(0, 100));
    },
    [],
  );

  const addAiThought = useCallback((thought: string) => {
    setAiThoughts((prev) =>
      [...prev, `[${new Date().toLocaleTimeString()}] ${thought}`].slice(-50),
    );
  }, []);

  const handleGameUpdate = useCallback((data: WsMessage | AiThoughtMsg) => {
    if (!data || typeof data !== "object") return;
    const { type, payload } = data;

    switch (type) {
      case "state_snapshot": {
        const p = (payload ?? null) as StatePayload | null;
        if (!p) return;
        setGameState(p as unknown as GameState);
        if (p.screenshotUrl) {
          setCurrentScreenshot(p.screenshotUrl);
        }
        if (p.chronicle_entries) {
          setChronicle(p.chronicle_entries);
        }
        break;
      }
      case "state_update": {
        const p = (payload ?? null) as StatePayload | null;
        if (!p) return;
        setGameState((prev) => ({ ...prev, ...p }));

        if (p.screenshotUrl) {
          setCurrentScreenshot(p.screenshotUrl);
        }

        if (p.session_id) {
          setCurrentSessionId(p.session_id);
        }

        if (p.chronicle_entries) {
          setChronicle(p.chronicle_entries);
        } else if (p.chronicle_update) {
          setChronicle((prev) => {
            const update = p.chronicle_update as ChronicleEntry;
            if (!update.id) {
              return [...prev, update];
            }
            const withoutDup = prev.filter((entry) => entry.id !== update.id);
            return [...withoutDup, update];
          });
        }
        break;
      }
      case "log_entry": {
        const p = payload as LogEntryPayload | undefined;
        if (!p || !p.text) return;
        const rawCategory =
          typeof p.category === "string" ? p.category : undefined;
        const category =
          rawCategory && isKnownLogCategory(rawCategory) ? rawCategory : "info";
        addLog(p.text, category);
        break;
      }
      case "vision_update":
        setVisionState({
          description:
            typeof (payload as VisionPayload)?.description === "string"
              ? ((payload as VisionPayload).description ?? null)
              : null,
          processing: Boolean((payload as VisionPayload)?.processing),
        });
        break;
      case "vision_status":
        setVisionState((prev) => ({
          description: prev.description,
          processing: Boolean((payload as VisionPayload)?.processing),
        }));
        break;
      case "ai_thought": {
        const p = payload as AiThoughtMsg["payload"] | undefined;
        if (!p || !p.thought) return;
        addAiThought(p.thought);
        break;
      }
      case "memory_write": {
        const p = payload as MemoryWritePayload | undefined;
        if (p?.text) {
          setMemoryWrite(p.text);
        }
        break;
      }
      case "ai_processing": {
        const p = payload as { status: string; model?: string } | undefined;
        if (p?.status) {
          setAiProcessing({
            status: p.status as "idle" | "thinking" | "complete" | "error",
            model: p.model,
          });
        }
        break;
      }
      case "session_start": {
        const p = payload as
          | { session_id: string; start_time: string }
          | undefined;
        if (p?.session_id) {
          setCurrentSessionId(p.session_id);
          addLog(`New session started: ${p.session_id}`, "system");
        }
        break;
      }
      default: {
        if (import.meta.env?.DEV) {
          console.warn("Unhandled message", data);
        }
      }
    }
  }, [addAiThought, addLog]);

  useEffect(() => {
    // Connect to WebSocket server for real-time updates
    const websocket = new WebSocket(WS_URL);
    setWs(websocket);

    websocket.onopen = () => {
      setWsConnected(true);
      addLog("Connected to Fire Emblem server", "system");
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleGameUpdate(data);
      } catch {
        // Silently ignore malformed messages
      }
    };

    websocket.onclose = () => {
      setWsConnected(false);
      addLog("Disconnected from server", "system");
    };

    return () => {
      websocket.close();
    };
  }, [addLog, handleGameUpdate]);

  return (
    <StreamOverlay
      gameState={gameState}
      wsConnected={wsConnected}
      logs={logs}
      aiThoughts={aiThoughts}
      currentScreenshot={currentScreenshot}
      chronicle={filteredChronicle}
      visionDescription={visionState.description}
      visionProcessing={visionState.processing}
      memoryWrite={memoryWrite}
      onMemoryWriteClear={() => setMemoryWrite(null)}
      currentSessionId={currentSessionId}
      showAllSessions={showAllSessions}
      onToggleAllSessions={() => setShowAllSessions((prev) => !prev)}
      aiProcessing={aiProcessing}
    />
  );
}

export default App;

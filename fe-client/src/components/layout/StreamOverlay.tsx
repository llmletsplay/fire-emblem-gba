import { useEffect, useRef } from "react";
import type {
  GameState,
  LogEntry,
  ChronicleEntry,
} from "../../types/gameTypes";
import type { UnitDisplay } from "../../types/display";
import { Header } from "./Header";
import { MainContent } from "./MainContent";
import { PartyBar } from "./PartyBar";
import { useThoughts } from "../../hooks/useThoughts";
import {
  buildChapterTreeState,
  transformUnits,
} from "../../utils/transformers";
import "./StreamOverlay.css";

interface StreamOverlayProps {
  gameState: GameState;
  wsConnected: boolean;
  logs: LogEntry[];
  aiThoughts: string[];
  currentScreenshot: string;
  chronicle: ChronicleEntry[];
  visionDescription: string | null;
  visionProcessing: boolean;
  memoryWrite: string | null;
  onMemoryWriteClear: () => void;
  currentSessionId?: string;
  showAllSessions?: boolean;
  onToggleAllSessions?: () => void;
  aiProcessing?: {
    status: "idle" | "thinking" | "complete" | "error";
    model?: string;
  };
}

export function StreamOverlay({
  gameState,
  wsConnected,
  aiThoughts,
  currentScreenshot,
  visionProcessing,
  memoryWrite,
  onMemoryWriteClear,
  aiProcessing,
}: StreamOverlayProps) {
  const { thoughts, addThought } = useThoughts();
  const lastProcessedIndexRef = useRef(-1);

  // AI is processing if thinking or vision is processing
  const isProcessing = aiProcessing?.status === "thinking" || visionProcessing;

  // Process only NEW thoughts (ones we haven't seen yet)
  useEffect(() => {
    for (
      let i = lastProcessedIndexRef.current + 1;
      i < aiThoughts.length;
      i++
    ) {
      addThought(aiThoughts[i], currentScreenshot || undefined);
    }
    if (aiThoughts.length > 0) {
      lastProcessedIndexRef.current = aiThoughts.length - 1;
    }
  }, [aiThoughts, currentScreenshot, addThought]);

  const chapterTree = buildChapterTreeState(gameState);

  // Use currentTeam from backend (live party data from RAM)
  // Falls back to units for backwards compatibility
  const units = gameState.currentTeam || gameState.units || [];
  const transformedUnits: UnitDisplay[] = transformUnits(
    units,
    gameState.selectedUnit?.id,
  );

  const chapterNumber = gameState.chapter?.number || "P";
  const chapterTitle = gameState.chapter?.title || "The Fall of Renais";
  const turnNumber = gameState.turn || gameState.turnNumber || 1;
  const phase = gameState.phase || "Player";
  const objective =
    gameState.objective ||
    gameState.chapter?.objective ||
    "Awaiting objective...";

  return (
    <div className="stream-overlay">
      <Header
        modelName={gameState.modelName || "Claude Opus 4.5"}
        chapterTree={chapterTree}
        actionCount={gameState.actions || 0}
        tokenCount={gameState.tokensUsed || 0}
        inputTokens={gameState.inputTokens}
      />

      <MainContent
        thoughts={thoughts}
        isProcessing={isProcessing}
        gameScreen={{
          screenshotUrl: gameState.screenshotUrl || null,
          isLive: wsConnected,
        }}
        infoBar={{
          chapterNumber,
          chapterTitle,
          turnNumber,
          phase,
          objective,
        }}
        memoryWrite={memoryWrite}
        onMemoryWriteClear={onMemoryWriteClear}
      />

      <PartyBar units={transformedUnits} />
    </div>
  );
}

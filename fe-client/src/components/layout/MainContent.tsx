import type {
  ThoughtEntry,
  GameScreenProps,
  InfoBarProps,
} from "../../types/display";
import { ThoughtLog } from "../thought-log/ThoughtLog";
import { GameScreen } from "../game-display/GameScreen";
import { InfoBar } from "../game-display/InfoBar";
import "./MainContent.css";

interface MainContentProps {
  thoughts: ThoughtEntry[];
  isProcessing: boolean;
  gameScreen: GameScreenProps;
  infoBar: InfoBarProps;
  memoryWrite: string | null;
  onMemoryWriteClear: () => void;
}

export function MainContent({
  thoughts,
  isProcessing,
  gameScreen,
  infoBar,
  memoryWrite,
  onMemoryWriteClear,
}: MainContentProps) {
  return (
    <div className="main-content">
      <aside className="main-content__left">
        <ThoughtLog
          entries={thoughts}
          isProcessing={isProcessing}
          memoryWrite={memoryWrite}
          onMemoryWriteClear={onMemoryWriteClear}
        />
      </aside>

      <main className="main-content__center">
        <GameScreen
          screenshotUrl={gameScreen.screenshotUrl}
          isLive={gameScreen.isLive}
        />
        <InfoBar
          chapterNumber={infoBar.chapterNumber}
          chapterTitle={infoBar.chapterTitle}
          turnNumber={infoBar.turnNumber}
          phase={infoBar.phase}
          objective={infoBar.objective}
        />
      </main>
    </div>
  );
}

/**
 * Display-specific types for the streaming overlay UI.
 * These types represent transformed data ready for rendering.
 */

export type AIStatus = "thinking" | "idle" | "error";

export type HPStatus = "healthy" | "wounded" | "critical";

export type RouteType = "eirika" | "ephraim" | "shared";

export type ChapterStatus = "completed" | "current" | "future";

export interface ThoughtSections {
  observation?: string;
  reasoning?: string;
  action?: string;
}

export interface ThoughtEntry {
  id: string;
  timestamp: Date;
  text: string;
  buttons: string[];
  tools: string[];
  screenshot?: string;
  sections?: ThoughtSections;
  actionButtons?: string[];
}

export interface UnitDisplay {
  id: string;
  name: string;
  unitClass: string;
  level: number;
  hp: number;
  maxHp: number;
  hpPercent: number;
  hpStatus: HPStatus;
  portraitUrl: string;
  spriteUrl: string;
  affiliation: "player" | "enemy" | "ally" | "neutral";
  weapon?: string;
  isSelected: boolean;
}

export interface ChapterNode {
  id: string;
  number: string;
  title: string;
  route: RouteType;
}

export interface ChapterTreeState {
  chapters: ChapterNode[];
  currentChapter: string;
  currentRoute: RouteType | null;
  completedChapters: string[];
}

export interface DisplayMetrics {
  turnNumber: number;
  actionCount: number;
  tokensUsed: number;
  elapsedTime: string;
}

export interface HeaderProps {
  modelName: string;
  chapterTree: ChapterTreeState;
  actionCount: number;
  tokenCount: number;
  inputTokens?: number;
}

export interface ThoughtLogProps {
  entries: ThoughtEntry[];
  isProcessing: boolean;
  memoryWrite: string | null;
  onMemoryWriteClear: () => void;
}

export interface GameScreenProps {
  screenshotUrl: string | null;
  isLive: boolean;
}

export interface InfoBarProps {
  chapterNumber: string;
  chapterTitle: string;
  turnNumber: number;
  phase: string;
  objective: string;
}

export interface UnitCardProps {
  unit: UnitDisplay;
  compact?: boolean;
}

export interface PartyBarProps {
  units: UnitDisplay[];
}

export interface BadgeProps {
  label: string;
  variant?: "default" | "action" | "tool" | "class" | "phase";
  size?: "sm" | "md";
}

export interface HPBarProps {
  current: number;
  max: number;
  showNumbers?: boolean;
  size?: "sm" | "md" | "lg";
}

export interface StatusIndicatorProps {
  status: AIStatus;
}

export interface ActionsCounterProps {
  count: number;
  tokenCount: number;
  inputTokens?: number;
}

export interface ChapterTreeProps {
  state: ChapterTreeState;
}

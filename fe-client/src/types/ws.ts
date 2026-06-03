// WebSocket payload typings mirroring server schema

export type LogCategory =
  | "action"
  | "battle"
  | "system"
  | "error"
  | "ai"
  | "combat"
  | "movement"
  | "analysis"
  | "info";

export interface LogEntryPayload {
  id?: number;
  text: string;
  category: LogCategory;
}

export interface VisionPayload {
  description?: string | null;
  processing?: boolean;
}

export interface MemoryWritePayload {
  text: string;
}

export interface StateUpdatePayload {
  runId?: string;
  providerName?: string;
  modelName?: string;
  flags?: Record<string, unknown>;
  // GameState fields merged in App.tsx
  [key: string]: unknown;
}

export type WsMessage =
  | { type: "state_update"; payload: StateUpdatePayload }
  | { type: "state_snapshot"; payload: StateUpdatePayload }
  | { type: "log_entry"; payload: LogEntryPayload }
  | { type: "vision_update"; payload: VisionPayload }
  | { type: "vision_status"; payload: VisionPayload }
  | { type: "memory_write"; payload: MemoryWritePayload }
  | { type?: string; payload?: unknown };

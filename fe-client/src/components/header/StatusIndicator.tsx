import type { StatusIndicatorProps } from "../../types/display";
import { PulsingDot } from "../shared/PulsingDot";
import "./StatusIndicator.css";

export function StatusIndicator({ status }: StatusIndicatorProps) {
  const labels: Record<typeof status, string> = {
    thinking: "CURRENTLY THINKING",
    idle: "IDLE",
    error: "ERROR",
  };

  const colors: Record<typeof status, "gold" | "green" | "red"> = {
    thinking: "gold",
    idle: "green",
    error: "red",
  };

  return (
    <div className={`status-indicator status-indicator--${status}`}>
      <PulsingDot
        color={colors[status]}
        size="sm"
        active={status === "thinking"}
      />
      <span className="status-indicator__label">{labels[status]}</span>
    </div>
  );
}

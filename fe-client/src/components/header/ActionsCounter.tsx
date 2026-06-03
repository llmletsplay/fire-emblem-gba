import type { ActionsCounterProps } from "../../types/display";
import { AnimatedCounter } from "./AnimatedCounter";
import "./ActionsCounter.css";

function formatTokens(tokens: number): string {
  if (tokens >= 1000000) {
    return `${(tokens / 1000000).toFixed(1)}M`;
  }
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(1)}K`;
  }
  return tokens.toLocaleString();
}

export function ActionsCounter({
  count,
  tokenCount,
  inputTokens,
}: ActionsCounterProps) {
  return (
    <div className="actions-counter">
      {inputTokens !== undefined && inputTokens > 0 && (
        <>
          <div className="actions-counter__stat">
            <AnimatedCounter
              value={inputTokens}
              formatFn={formatTokens}
              className="actions-counter__value actions-counter__value--input"
            />
            <span className="actions-counter__label">input</span>
          </div>
          <div className="actions-counter__divider" />
        </>
      )}
      <div className="actions-counter__stat">
        <AnimatedCounter
          value={tokenCount}
          formatFn={formatTokens}
          className="actions-counter__value"
        />
        <span className="actions-counter__label">output</span>
      </div>
      <div className="actions-counter__divider" />
      <div className="actions-counter__stat">
        <AnimatedCounter value={count} className="actions-counter__value" />
        <span className="actions-counter__label">actions</span>
      </div>
    </div>
  );
}

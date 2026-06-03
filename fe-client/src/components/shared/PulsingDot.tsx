import "./PulsingDot.css";

interface PulsingDotProps {
  color?: "gold" | "green" | "red" | "blue";
  size?: "sm" | "md" | "lg";
  active?: boolean;
}

export function PulsingDot({
  color = "gold",
  size = "md",
  active = true,
}: PulsingDotProps) {
  return (
    <span
      className={`pulsing-dot pulsing-dot--${color} pulsing-dot--${size} ${active ? "pulsing-dot--active" : ""}`}
    />
  );
}

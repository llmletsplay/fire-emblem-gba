import type { BadgeProps } from "../../types/display";
import "./Badge.css";

export function Badge({ label, variant = "default", size = "md" }: BadgeProps) {
  return (
    <span className={`badge badge--${variant} badge--${size}`}>{label}</span>
  );
}

import "./ClassBadge.css";

interface ClassBadgeProps {
  unitClass: string;
  size?: "sm" | "md";
}

export function ClassBadge({ unitClass, size = "sm" }: ClassBadgeProps) {
  return (
    <span className={`class-badge class-badge--${size}`}>
      {unitClass.toUpperCase()}
    </span>
  );
}

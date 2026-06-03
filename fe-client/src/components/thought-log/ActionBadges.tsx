import { Badge } from "../shared/Badge";
import "./ActionBadges.css";

interface ActionBadgesProps {
  buttons: string[];
  tools: string[];
}

export function ActionBadges({ buttons, tools }: ActionBadgesProps) {
  if (buttons.length === 0 && tools.length === 0) {
    return null;
  }

  return (
    <div className="action-badges">
      {buttons.map((button) => (
        <Badge key={button} label={button} variant="action" size="sm" />
      ))}
      {tools.map((tool) => (
        <Badge key={tool} label={tool} variant="tool" size="sm" />
      ))}
    </div>
  );
}

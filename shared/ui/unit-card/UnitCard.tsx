import type { UnitCardProps } from "./types";
import { UnitPortrait } from "./UnitPortrait";
import { HPBar } from "./HPBar";
import { ClassSprite } from "./ClassSprite";
import "./UnitCard.css";

export function UnitCard({
  unit,
  compact = false,
  showHP = true,
  showClass = true,
  onClick,
}: UnitCardProps) {
  const affiliationClass =
    unit.affiliation === "enemy"
      ? "enemy"
      : unit.affiliation === "ally"
        ? "ally"
        : "player";

  const handleClick = onClick ? () => onClick(unit) : undefined;

  return (
    <div
      className={`unit-card unit-card--${affiliationClass} ${compact ? "unit-card--compact" : ""} ${onClick ? "unit-card--clickable" : ""}`}
      onClick={handleClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <UnitPortrait src={unit.portraitUrl} name={unit.name} size="md" />

      <div className="unit-card__info">
        <div className="unit-card__header">
          <span className="unit-card__name">{unit.name}</span>
          <span className="unit-card__level">Lv.{unit.level}</span>
        </div>

        {showHP && (
          <HPBar
            current={unit.hp}
            max={unit.maxHp}
            showNumbers={!compact}
            size={compact ? "sm" : "md"}
          />
        )}

        {showClass && (
          <div className="unit-card__class-row">
            <ClassSprite src={unit.spriteUrl} alt={unit.unitClass} size="sm" />
            <span className="unit-card__class-name">{unit.unitClass}</span>
          </div>
        )}
      </div>
    </div>
  );
}

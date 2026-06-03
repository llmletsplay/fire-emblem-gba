/**
 * UnitCard component for displaying Fire Emblem character info.
 *
 * A shared version of this component exists at /shared/ui/unit-card
 * for use in fe-web (documentation site).
 */

import type { UnitCardProps } from "../../types/display";
import { UnitPortrait } from "./UnitPortrait";
import { HPBar } from "./HPBar";
import { ClassSprite } from "./ClassSprite";
import "./UnitCard.css";

export function UnitCard({ unit, compact = false }: UnitCardProps) {
  const affiliationClass =
    unit.affiliation === "enemy"
      ? "enemy"
      : unit.affiliation === "ally"
        ? "ally"
        : "player";

  return (
    <div
      className={`unit-card unit-card--${affiliationClass} ${compact ? "unit-card--compact" : ""}`}
    >
      <UnitPortrait src={unit.portraitUrl} name={unit.name} size="md" />

      <div className="unit-card__info">
        <div className="unit-card__header">
          <span className="unit-card__name">{unit.name}</span>
          <span className="unit-card__level">Lv.{unit.level}</span>
        </div>

        <HPBar
          current={unit.hp}
          max={unit.maxHp}
          showNumbers={!compact}
          size={compact ? "sm" : "md"}
        />

        <div className="unit-card__class-row">
          <ClassSprite src={unit.spriteUrl} alt={unit.unitClass} size="sm" />
          <span className="unit-card__class-name">{unit.unitClass}</span>
        </div>
      </div>
    </div>
  );
}

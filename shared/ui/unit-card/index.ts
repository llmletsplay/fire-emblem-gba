/**
 * Shared UnitCard component for displaying Fire Emblem character cards.
 * Can be used in both fe-client (streaming overlay) and fe-web (documentation).
 */

export { UnitCard } from "./UnitCard";
export { UnitPortrait } from "./UnitPortrait";
export { HPBar } from "./HPBar";
export { ClassSprite } from "./ClassSprite";
export { getHPStatus, getHPPercent } from "./utils";
export type {
  UnitData,
  UnitCardProps,
  UnitPortraitProps,
  HPBarProps,
  ClassSpriteProps,
  HPStatus,
  Affiliation,
} from "./types";

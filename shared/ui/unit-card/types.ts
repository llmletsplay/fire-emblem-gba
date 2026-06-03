/**
 * Shared types for the UnitCard component.
 * These can be used by both fe-client and fe-web.
 */

export type HPStatus = "healthy" | "wounded" | "critical";

export type Affiliation = "player" | "enemy" | "ally" | "neutral";

export interface UnitData {
  id: string;
  name: string;
  unitClass: string;
  level: number;
  hp: number;
  maxHp: number;
  portraitUrl: string;
  spriteUrl: string;
  affiliation: Affiliation;
  weapon?: string;
}

export interface UnitCardProps {
  unit: UnitData;
  compact?: boolean;
  showHP?: boolean;
  showClass?: boolean;
  onClick?: (unit: UnitData) => void;
}

export interface UnitPortraitProps {
  src: string;
  name: string;
  size?: "sm" | "md" | "lg";
}

export interface HPBarProps {
  current: number;
  max: number;
  showNumbers?: boolean;
  size?: "sm" | "md" | "lg";
}

export interface ClassSpriteProps {
  src: string;
  alt: string;
  size?: "sm" | "md" | "lg";
}

/**
 * Utility functions for the UnitCard component.
 */

import type { HPStatus } from "./types";

export function getHPStatus(hp: number, maxHp: number): HPStatus {
  const percent = (hp / maxHp) * 100;
  if (percent <= 25) return "critical";
  if (percent <= 50) return "wounded";
  return "healthy";
}

export function getHPPercent(hp: number, maxHp: number): number {
  return Math.max(0, Math.min(100, (hp / maxHp) * 100));
}

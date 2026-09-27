"""Small zero-sum combat selector for FE7 Link Arena.

The policy searches the current unit/weapon matchup and assumes the opposing
player chooses the counterweapon that gives the agent the worst exchange. The
combat rates are an evaluation model; the game remains authoritative for the
actual battle and RNG.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Weapon:
    item_id: int
    name: str
    might: int
    hit: int
    weight: int
    crit: int = 0
    kind: str = "physical"
    brave: bool = False
    drain: bool = False
    effective: frozenset[int] = frozenset()


# Stats used by the five-unit teams in the selected Link Arena save, plus the
# standard weapons that can appear in those inventories.
WEAPONS: dict[int, Weapon] = {
    0x01: Weapon(0x01, "Iron Sword", 5, 90, 5, kind="sword"),
    0x03: Weapon(0x03, "Steel Sword", 8, 75, 10, kind="sword"),
    0x04: Weapon(0x04, "Silver Sword", 13, 80, 8, kind="sword"),
    0x0B: Weapon(0x0B, "Brave Sword", 9, 75, 12, kind="sword", brave=True),
    0x0D: Weapon(0x0D, "Killing Edge", 9, 75, 7, crit=30, kind="sword"),
    0x14: Weapon(0x14, "Iron Lance", 7, 80, 8, kind="lance"),
    0x17: Weapon(0x17, "Silver Lance", 14, 75, 10, kind="lance"),
    0x19: Weapon(0x19, "Brave Lance", 10, 70, 11, kind="lance", brave=True),
    0x1A: Weapon(0x1A, "Killer Lance", 9, 70, 9, crit=30, kind="lance"),
    0x1C: Weapon(0x1C, "Javelin", 6, 65, 11, kind="lance"),
    0x1E: Weapon(0x1E, "Axereaver", 9, 80, 11, kind="lance"),
    0x1F: Weapon(0x1F, "Iron Axe", 8, 75, 10, kind="axe"),
    0x21: Weapon(0x21, "Silver Axe", 15, 70, 15, kind="axe"),
    0x23: Weapon(0x23, "Brave Axe", 10, 60, 10, kind="axe", brave=True),
    0x24: Weapon(0x24, "Killer Axe", 11, 65, 14, crit=30, kind="axe"),
    0x28: Weapon(0x28, "Hand Axe", 7, 60, 12, kind="axe"),
    0x2A: Weapon(0x2A, "Swordreaver", 9, 75, 11, kind="axe"),
    0x2B: Weapon(0x2B, "Swordslayer", 11, 75, 11, kind="axe"),
    0x2C: Weapon(0x2C, "Iron Bow", 6, 85, 5, kind="bow"),
    0x2E: Weapon(0x2E, "Silver Bow", 13, 75, 9, kind="bow"),
    0x30: Weapon(0x30, "Killer Bow", 9, 75, 7, crit=30, kind="bow"),
    0x31: Weapon(0x31, "Brave Bow", 10, 65, 12, kind="bow", brave=True),
    0x37: Weapon(0x37, "Fire", 5, 90, 4, kind="anima"),
    0x39: Weapon(0x39, "Elfire", 10, 85, 10, kind="anima"),
    0x3B: Weapon(0x3B, "Fimbulvetr", 13, 80, 12, kind="anima"),
    0x3D: Weapon(0x3D, "Excalibur", 18, 90, 13, crit=10, kind="anima"),
    0x40: Weapon(0x40, "Divine", 8, 90, 6, kind="light"),
    0x42: Weapon(0x42, "Aura", 17, 70, 15, kind="light"),
    0x45: Weapon(0x45, "Luna", 0, 95, 12, kind="dark"),
    0x46: Weapon(0x46, "Nosferatu", 8, 70, 14, kind="dark", drain=True),
    0x48: Weapon(0x48, "Fenrir", 20, 65, 20, kind="dark"),
    0x49: Weapon(0x49, "Gespenst", 23, 70, 18, kind="dark"),
    # FE7's unused-looking 0x77 entry is Vaida's Uber Spear. Its item name is
    # shortened by the Link Arena UI, but the GBA ROM still applies it as a
    # normal, selectable lance.
    0x77: Weapon(0x77, "Uber Spear", 12, 70, 10, crit=5, kind="lance"),
    0x85: Weapon(0x85, "Armads", 18, 75, 18, crit=5, kind="axe"),
    0x8D: Weapon(0x8D, "Wolf Beil", 10, 75, 10, kind="axe", effective=frozenset({0x16, 0x28, 0x2A})),
    0x90: Weapon(0x90, "Regal Blade", 9, 85, 8, kind="sword"),
    0x91: Weapon(0x91, "Rex Hasta", 18, 85, 11, kind="lance"),
    0x92: Weapon(0x92, "Basilikos", 22, 85, 13, crit=5, kind="axe"),
    0x93: Weapon(0x93, "Rienfleche", 15, 70, 12, kind="bow"),
    0x94: Weapon(0x94, "Luce", 16, 80, 11, kind="light"),
    0x95: Weapon(0x95, "Gespenst", 23, 70, 18, kind="dark"),
}

CLASS_CON: dict[int, int] = {
    0x09: 11,  # Great Lord
    0x13: 13,  # Warrior
    0x16: 15,  # General
    0x26: 8,   # Druid
}

WEAPON_TRIANGLE = {"sword": "axe", "axe": "lance", "lance": "sword"}
MAGIC_TRIANGLE = {"anima": "light", "light": "dark", "dark": "anima"}


def _ival(unit: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(unit.get(key, default))
    except (TypeError, ValueError):
        return default


def _hp(unit: dict[str, Any]) -> tuple[int, int]:
    value = unit.get("hp", {})
    if not isinstance(value, dict):
        return 0, 1
    return _ival(value, "current"), max(1, _ival(value, "max", 1))


def weapons_for(unit: dict[str, Any]) -> list[tuple[int, Weapon]]:
    result: list[tuple[int, Weapon]] = []
    inventory = unit.get("inventory", [])
    if not isinstance(inventory, list):
        return result
    for item in inventory:
        if not isinstance(item, dict) or _ival(item, "uses") == 0:
            continue
        item_id = _ival(item, "id")
        weapon = WEAPONS.get(item_id)
        if weapon is not None:
            result.append((_ival(item, "slot"), weapon))
    return result


def _display_hit(attacker: dict[str, Any], defender: dict[str, Any], weapon: Weapon) -> int:
    raw = (
        weapon.hit
        + 2 * _ival(attacker, "skill")
        + _ival(attacker, "luck") // 2
        - (2 * _ival(defender, "speed") + _ival(defender, "luck"))
    )
    return max(0, min(100, raw))


def _true_hit(display_hit: int) -> float:
    # FE7 uses two random numbers for hit. This is the area-under-the-diagonal
    # probability for two 0..99 rolls whose average is below displayed hit.
    p = display_hit / 100.0
    return 2 * p * p if p <= 0.5 else 1 - 2 * (1 - p) * (1 - p)


def _triangle(attacker: Weapon, defender: Weapon) -> int:
    if WEAPON_TRIANGLE.get(attacker.kind) == defender.kind:
        return 1
    if WEAPON_TRIANGLE.get(defender.kind) == attacker.kind:
        return -1
    if MAGIC_TRIANGLE.get(attacker.kind) == defender.kind:
        return 1
    if MAGIC_TRIANGLE.get(defender.kind) == attacker.kind:
        return -1
    return 0


def expected_damage(
    attacker: dict[str, Any], defender: dict[str, Any], weapon: Weapon,
    defender_weapon: Weapon | None = None,
) -> float:
    power = _ival(attacker, "strength") + weapon.might
    defense = _ival(defender, "resistance") if weapon.kind in {"anima", "light", "dark"} else _ival(defender, "defense")
    if weapon.name == "Luna":
        defense = 0
    triangle = _triangle(weapon, defender_weapon) if defender_weapon else 0
    power += triangle
    if _ival(defender, "class_id") in weapon.effective:
        power *= 3
    damage = max(0, power - defense)

    hit = _display_hit(attacker, defender, weapon) + (15 if triangle > 0 else -15 if triangle < 0 else 0)
    hit = max(0, min(100, hit))
    hit_probability = _true_hit(hit)
    critical = max(0, min(100, weapon.crit + _ival(attacker, "skill") // 2 - _ival(defender, "luck") // 2)) / 100.0

    con = CLASS_CON.get(_ival(attacker, "class_id"), 10) + _ival(attacker, "constitution_bonus")
    attack_speed = _ival(attacker, "speed") - max(0, weapon.weight - con)
    defender_con = CLASS_CON.get(_ival(defender, "class_id"), 10) + _ival(defender, "constitution_bonus")
    defender_speed = _ival(defender, "speed") - max(0, (defender_weapon.weight - defender_con) if defender_weapon else 0)
    attacks = (2 if attack_speed - defender_speed >= 4 else 1) * (2 if weapon.brave else 1)

    per_hit = damage * hit_probability * (1 + 2 * critical)
    if weapon.drain:
        per_hit *= 1.15
    return per_hit * attacks


@dataclass(frozen=True)
class DuelChoice:
    attacker_id: int
    defender_id: int
    item_id: int
    slot: int
    score: float
    worst_reply_item: int | None


def minimax_weapon(
    attacker: dict[str, Any], defender: dict[str, Any],
    *, defender_auto_weapon: bool = True,
) -> tuple[int, Weapon, float, int | None]:
    """Return the weapon with the best worst-case exchange for one matchup."""
    choices = weapons_for(attacker)
    if not choices:
        raise ValueError("selected Link Arena unit has no recognized weapons")
    replies = weapons_for(defender) if not defender_auto_weapon else []
    if not replies:
        replies = [(0, None)]  # type: ignore[list-item]

    best: tuple[int, Weapon, float, int | None] | None = None
    for slot, weapon in choices:
        outcomes: list[tuple[float, int | None]] = []
        for _, reply in replies:
            inflicted = expected_damage(attacker, defender, weapon, reply)
            returned = expected_damage(defender, attacker, reply) if reply else 0.0
            defender_hp, _ = _hp(defender)
            attacker_hp, _ = _hp(attacker)
            # Survival points reward preventing a loss more than ordinary damage.
            score = inflicted - 0.9 * returned
            if inflicted >= defender_hp:
                score += 65
            if returned >= attacker_hp:
                score -= 75
            outcomes.append((score, reply.item_id if reply else None))
        worst_score, reply_id = min(outcomes, key=lambda entry: entry[0])
        item_id = weapon.item_id
        candidate = (slot, weapon, worst_score, reply_id)
        if best is None or candidate[2] > best[2] or (candidate[2] == best[2] and item_id < best[1].item_id):
            best = candidate
    assert best is not None
    return best


def minimax_matchup(
    own_units: Iterable[dict[str, Any]], opponent_units: Iterable[dict[str, Any]],
    *, defender_auto_weapon: bool = True,
) -> DuelChoice:
    """Search attacker, target, weapon, then the opponent's best counterweapon."""
    own = list(own_units)
    opponents = list(opponent_units)
    if not own or not opponents:
        raise ValueError("both sides need at least one live unit")

    best_choice: DuelChoice | None = None
    for attacker in own:
        attacker_hp, _ = _hp(attacker)
        if attacker_hp <= 0:
            continue
        for defender in opponents:
            defender_hp, _ = _hp(defender)
            if defender_hp <= 0:
                continue
            try:
                slot, weapon, score, reply = minimax_weapon(
                    attacker, defender, defender_auto_weapon=defender_auto_weapon
                )
            except ValueError:
                continue
            candidate = DuelChoice(
                attacker_id=_ival(attacker, "character_id"),
                defender_id=_ival(defender, "character_id"),
                item_id=weapon.item_id,
                slot=slot,
                score=score,
                worst_reply_item=reply,
            )
            if best_choice is None or candidate.score > best_choice.score:
                best_choice = candidate

    if best_choice is None:
        raise ValueError("no legal FE7 weapon matchup found")
    return best_choice

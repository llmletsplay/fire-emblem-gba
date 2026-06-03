"""
Movement Range Calculator - Computes valid movement tiles from unit stats.

This provides deterministic movement tile calculation based on:
- Unit's base movement stat
- Class movement bonus
- Terrain costs (roads, plains, forests, mountains, etc.)
"""

from typing import List, Tuple, Set, Dict
from collections import deque


# Terrain movement costs (FE7/FE8 standard)
TERRAIN_COSTS = {
    0x00: 1,  # Plain
    0x01: 1,  # Road
    0x02: 2,  # Forest
    0x03: 1,  # Mountain (cavalry can't enter)
    0x04: 1,  # Hill
    0x05: 99, # Lake (cavalry can't enter)
    0x06: 1,  # Wall (impassable)
    0x07: 1,  # Fort (defensive tile)
    0x08: 99, # River (impassable)
    0x09: 1,  # Sand
    0x0A: 1,  # Dense forest
    0x0B: 1,  # Roof (not used much)
    0x0C: 1,  # Pillar (impassable)
    0x0D: 1,  # Gate
    0x0E: 1,  # Barrel (destructible)
    0x0F: 1,  # Chest
    # Add more as needed
}


# Class movement bonuses (promoted classes get +1 or +2 movement)
CLASS_MOVEMENT_BONUS = {
    # FE7 classes
    "Paladin": 1,
    "Great Knight": 1,
    "General": 1,
    "Hero": 1,
    "Swordmaster": 1,
    "Assassin": 1,
    "Berserker": 1,
    "Warrior": 1,
    "Sniper": 1,
    "Marksman": 1,
    "Bishop": 1,
    "Sage": 1,
    "Druid": 1,
    "Nightingale": 1,
    "Falken": 1,
    "Petrine": 1,
    "Janal": 1,
    # FE8 classes
    "Great Lord": 1,
    "Master Knight": 1,
    "Berserker": 1,
    "Reaver": 1,
    "Swordmaster": 1,
    "Rogue": 1,
    "Necromancer": 1,
    "Summoner": 1,
    "Grail Knight": 1,
    "Vanquisher": 1,
    "Orion": 1,
    "Hippogriff Knight": 1,
    "Harpy": 1,
    "Phoenix": 1,
    "Giant": 1,
    "Druid": 1,
    "Demon King": 1,
}


# Base movement by class type
CLASS_BASE_MOVEMENT = {
    # Infantry (most common)
    "Lord": 5,
    "Mercenary": 5,
    "Myrmidon": 5,
    "Fighter": 5,
    "Archer": 5,
    "Monk": 5,
    "Cleric": 5,
    "Mage": 5,
    "Shaman": 5,
    "Knight": 4,
    "Armor": 4,
    "Thief": 6,
    "Dancer": 5,
    "Bard": 5,
    # Cavalry
    "Cavalier": 7,
    "Paladin": 8,
    "Great Knight": 7,
    "Armor Knight": 5,
    # Flying
    "Pegasus Knight": 6,
    "Falcon Knight": 7,
    "Wyvern Rider": 6,
    "Wyvern Knight": 7,
    "Wyvern Lord": 7,
    "Griffin": 7,
    "Hippogriff": 7,
    # Other
    "Nomad": 7,
    "Nomad Trooper": 8,
    "Warrior": 5,
    "Sniper": 5,
    "General": 4,
}


def get_unit_movement(unit_class: str, mov_bonus: int = 0) -> int:
    """
    Get unit's total movement range.
    
    Args:
        unit_class: The class name (e.g., "Fighter", "Paladin")
        mov_bonus: Movement bonus from items/terrain (from unit data)
    
    Returns:
        Total movement range in tiles
    """
    base = CLASS_BASE_MOVEMENT.get(unit_class, 5)
    bonus = CLASS_MOVEMENT_BONUS.get(unit_class, 0)
    return base + bonus + mov_bonus


def calculate_movement_tiles(
    unit_x: int,
    unit_y: int,
    movement: int,
    map_width: int = 16,
    map_height: int = 16,
    terrain_map: Dict[Tuple[int, int], int] = None,
    occupied_tiles: Set[Tuple[int, int]] = None,
) -> List[Tuple[int, int]]:
    """
    Calculate all reachable tiles for a unit using BFS.
    
    Args:
        unit_x: Unit's current X position
        unit_y: Unit's current Y position  
        movement: Unit's movement stat
        map_width: Width of the map in tiles
        map_height: Height of the map in tiles
        terrain_map: Dict mapping (x,y) -> terrain type (for custom costs)
        occupied_tiles: Set of (x,y) tiles occupied by other units
    
    Returns:
        List of reachable (x,y) tile positions
    """
    if occupied_tiles is None:
        occupied_tiles = set()
    
    if terrain_map is None:
        terrain_map = {}
    
    reachable = []
    visited = set()
    queue = deque([(unit_x, unit_y, 0)])  # x, y, cost
    visited.add((unit_x, unit_y))
    
    # 4-directional movement (no diagonals in FE)
    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
    
    while queue:
        x, y, cost = queue.popleft()
        
        # Don't include starting position
        if (x, y) != (unit_x, unit_y):
            reachable.append((x, y))
        
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            
            # Check bounds
            if nx < 0 or nx >= map_width or ny < 0 or ny >= map_height:
                continue
            
            if (nx, ny) in visited:
                continue
                
            # Check if occupied by another unit
            if (nx, ny) in occupied_tiles:
                continue
            
            # Get terrain cost
            terrain = terrain_map.get((nx, ny), 0)  # Default to plain
            move_cost = TERRAIN_COSTS.get(terrain, 1)
            
            # Check if within movement range
            new_cost = cost + move_cost
            if new_cost <= movement:
                visited.add((nx, ny))
                queue.append((nx, ny, new_cost))
    
    return reachable


def get_weapon_range(weapon_type: str) -> Tuple[int, int]:
    """
    Get weapon's attack range (min, max).
    
    Args:
        weapon_type: One of "Sword", "Lance", "Axe", "Bow", "Staff", "Anima", "Light", "Dark"
                     or weapon name like "Iron Bow", "Steel Axe", etc.
    
    Returns:
        Tuple of (min_range, max_range)
    """
    weapon_type = weapon_type.lower() if weapon_type else ""
    
    # Ranged weapons
    if "bow" in weapon_type:
        return (2, 2)  # Bows can't attack adjacent
    if "staff" in weapon_type:
        return (1, 2)  # Staffs have 1-2 range
    if "anima" in weapon_type or "light" in weapon_type or "dark" in weapon_type:
        return (1, 2)  # Magic has 1-2 range
    
    # Throwable weapons (axes, javelins)
    if "hand axe" in weapon_type or "javelin" in weapon_type:
        return (2, 2)
    
    # Melee weapons (default)
    return (1, 1)


def get_adjacent_enemy_tiles(
    unit_x: int,
    unit_y: int,
    enemies: List[Dict],
    weapon_range: Tuple[int, int] = (1, 1),
) -> List[Tuple[int, int]]:
    """
    Get tiles from which unit can attack enemies.
    
    Args:
        unit_x: Unit's X position
        unit_y: Unit's Y position
        enemies: List of enemy dicts with 'x', 'y' fields
        weapon_range: Tuple of (min_range, max_range)
    
    Returns:
        List of (x,y) tiles that can attack enemies
    """
    min_range, max_range = weapon_range
    attack_tiles = []
    
    for enemy in enemies:
        ex, ey = enemy.get("x", 0), enemy.get("y", 0)
        distance = abs(ex - unit_x) + abs(ey - unit_y)
        
        if min_range <= distance <= max_range:
            # Find adjacent tiles to enemy within range
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                ax, ay = ex + dx, ey + dy
                dist_from_unit = abs(ax - unit_x) + abs(ay - unit_y)
                if dist_from_unit <= max_range:
                    attack_tiles.append((ax, ay))
    
    return attack_tiles
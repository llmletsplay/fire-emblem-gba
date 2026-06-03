export type Phase = "Player" | "Enemy" | "Ally";

export type UnitClass =
  | "Lord"
  | "Great Lord"
  | "Cavalier"
  | "Paladin"
  | "Great Knight"
  | "Knight"
  | "General"
  | "Myrmidon"
  | "Swordmaster"
  | "Mercenary"
  | "Hero"
  | "Fighter"
  | "Warrior"
  | "Archer"
  | "Sniper"
  | "Ranger"
  | "Mage"
  | "Sage"
  | "Monk"
  | "Bishop"
  | "Shaman"
  | "Druid"
  | "Priest"
  | "Cleric"
  | "Troubadour"
  | "Valkyrie"
  | "Thief"
  | "Rogue"
  | "Assassin"
  | "Pegasus Knight"
  | "Falcoknight"
  | "Wyvern Rider"
  | "Wyvern Lord"
  | "Wyvern Knight"
  | "Brigand"
  | "Pirate"
  | "Berserker"
  | "Soldier"
  | "Dancer"
  | "Manakete"
  | "Necromancer"
  | "Summoner"
  | "Demon King";

export type WeaponType =
  | "Sword"
  | "Lance"
  | "Axe"
  | "Bow"
  | "Anima"
  | "Light"
  | "Dark"
  | "Staff"
  | "Dragonstone";

export type WeaponRank = "-" | "E" | "D" | "C" | "B" | "A" | "S";

export interface Weapon {
  name: string;
  type: WeaponType;
  might: number;
  hit: number;
  crit: number;
  weight: number;
  uses: number;
  currentUses: number;
  range: [number, number];
  specialEffect?: string;
}

export interface Unit {
  id: string;
  name: string;
  unitClass: UnitClass;
  level: number;
  exp?: number;

  // Current/Max Stats
  hp: number;
  maxHp: number;

  // Combat Stats
  strength?: number;
  magic?: number;
  skill?: number;
  speed?: number;
  luck?: number;
  defense?: number;
  resistance?: number;
  constitution?: number;
  movement?: number;

  // Position
  x: number;
  y: number;

  // Equipment
  weapon?: string;
  items?: Weapon[];
  equippedIndex?: number;

  // Weapon Proficiency
  weaponRanks?: Record<WeaponType, WeaponRank>;

  // Status
  affiliation?: "player" | "enemy" | "ally" | "neutral";
  hasMoved?: boolean;
  hasActed?: boolean;
  rescuedUnit?: string; // ID of rescued unit

  // Support
  affinity?: string;
  supportLevels?: Record<string, number>;
}

export interface TerrainInfo {
  type: string;
  avoidBonus: number;
  defenseBonus: number;
  healPercentage: number;
  movementCost: Record<string, number>;
}

export interface BattleForecast {
  attacker: {
    unit: Unit;
    damage: number;
    hit: number;
    crit: number;
    doubles: boolean;
  };
  defender: {
    unit: Unit;
    damage: number;
    hit: number;
    crit: number;
    doubles: boolean;
  };
}

export interface Chapter {
  number: string;
  title: string;
  objective: string;
  turnLimit?: number;
  currentWeather?: string;
  fogOfWar: boolean;
}

export interface GameState {
  // Chapter Info
  chapterId?: string;
  chapter?: Chapter;
  turnNumber?: number;
  turn?: number;
  phase?: Phase;

  // Objectives
  objective?: string;
  primaryGoal?: string;
  secondaryGoal?: string;
  tertiaryGoal?: string;
  otherNotes?: string;

  // Map Info
  mapWidth?: number;
  mapHeight?: number;
  cursorPosition?: [number, number];
  cameraPosition?: [number, number];

  // Units
  units?: Unit[];
  currentTeam?: Unit[]; // Party members from backend (live from RAM)
  playerUnits?: Unit[];
  enemyUnits?: Unit[];
  allyUnits?: Unit[];
  enemyCount?: number;
  allyCount?: number;

  // Current State
  selectedUnit?: Unit;
  hoveredTerrain?: TerrainInfo;
  battleForecast?: BattleForecast;
  actions?: number;
  tokens?: number;
  tokensUsed?: number;
  inputTokens?: number;
  gameStatus?: string;
  modelName?: string;

  // UI State
  inMenu?: boolean;
  menuType?: string;

  // Display
  screenshotUrl?: string;
  minimapUrl?: string;
  llmMetrics?: {
    p50LatencySec?: number;
    p95LatencySec?: number;
    successRate?: number; // 0..1
  };
}

export interface LogEntry {
  id?: number;
  timestamp: string;
  type:
    | "action"
    | "battle"
    | "system"
    | "error"
    | "ai"
    | "combat"
    | "movement"
    | "info";
  message: string;
}

export interface ChronicleEntry {
  id?: string;
  session_id?: string;
  timestamp: string;
  chapter?: string | null;
  phase?: string;
  interpretation?: string;
  narrative?: string;
  summary?: string;
  screenshot?: string;
  screenshot_url?: string;
  actions?: string[];
}

export interface SessionInfo {
  session_id: string;
  start_time: string;
  end_time?: string;
  chapter_start?: string;
  chapter_current?: string;
  total_actions: number;
  status: "active" | "completed" | "interrupted";
  screenshot_count: number;
}

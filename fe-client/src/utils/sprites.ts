/**
 * Sprite and portrait URL resolution utilities.
 * Centralized asset path management for Fire Emblem units.
 */

const CLASS_SPRITES: Record<string, string> = {
  lord: "Ma_gba_lord_eirika_playable.gif",
  "lord (eirika)": "Ma_gba_lord_eirika_playable.gif",
  "lord (ephraim)": "Ma_gba_lord_ephraim_playable.gif",
  "great lord": "Ma_gba_great_lord_eirika_playable.gif",
  "great lord (eirika)": "Ma_gba_great_lord_eirika_playable.gif",
  "great lord (ephraim)": "Ma_gba_great_lord_ephraim_playable.gif",
  cavalier: "Ma_gba_cavalier_playable.gif",
  paladin: "Ma_gba_paladin_playable.gif",
  "great knight": "Ma_gba_great_knight_playable.gif",
  troubadour: "Ma_gba_troubadour_playable.gif",
  valkyrie: "Ma_gba_valkyrie_playable.gif",
  ranger: "Ma_gba_ranger_playable.gif",
  "mage knight": "Ma_gba_mage_knight_playable.gif",
  myrmidon: "Ma_gba_myrmidon_playable.gif",
  swordmaster: "Ma_gba_swordmaster_playable.gif",
  mercenary: "Ma_gba_mercenary_playable.gif",
  hero: "Ma_gba_hero_playable.gif",
  thief: "Ma_gba_thief_playable.gif",
  rogue: "Ma_gba_rogue_playable.gif",
  assassin: "Ma_gba_assassin_playable.gif",
  fighter: "Ma_gba_fighter_playable.gif",
  warrior: "Ma_gba_warrior_playable.gif",
  berserker: "Ma_gba_berserker_playable.gif",
  journeyman: "Ma_gba_journeyman_playable.gif",
  pirate: "Ma_gba_berserker_playable.gif",
  knight: "Ma_gba_knight_playable.gif",
  general: "Ma_gba_general_playable.gif",
  archer: "Ma_gba_archer_female_playable.gif",
  sniper: "Ma_gba_sniper_playable.gif",
  "pegasus knight": "Ma_gba_pegasus_knight_playable.gif",
  falcoknight: "Ma_gba_falcoknight_playable.gif",
  "wyvern rider": "Ma_gba_wyvern_rider_playable.gif",
  "wyvern lord": "Ma_gba_wyvern_lord_playable.gif",
  "wyvern knight": "Ma_gba_wyvern_lord_playable.gif",
  mage: "Ma_gba_mage_playable.gif",
  sage: "Ma_gba_sage_playable.gif",
  pupil: "Ma_gba_mage_playable.gif",
  shaman: "Ma_gba_druid_playable.gif",
  druid: "Ma_gba_druid_playable.gif",
  summoner: "Ma_gba_summoner_playable.gif",
  cleric: "Ma_gba_cleric_playable.gif",
  priest: "Ma_gba_monk_playable.gif",
  monk: "Ma_gba_monk_playable.gif",
  bishop: "Ma_gba_bishop_playable.gif",
  dancer: "Ma_gba_dancer_tethys_playable.gif",
  manakete: "Ma_gba_manakete_myrrh_playable.gif",
  recruit: "Ma_gba_journeyman_playable.gif",
  soldier: "Ma_gba_soldier_enemy.gif",
  brigand: "Ma_gba_brigand_enemy.gif",
  revenant: "Ma_gba_revenant_enemy.gif",
  entombed: "Ma_gba_revenant_enemy.gif",
  bonewalker: "Ma_gba_soldier_enemy.gif",
  mogall: "Ma_gba_mogall_enemy.gif",
  "arch mogall": "Ma_gba_mogall_enemy.gif",
  gargoyle: "Ma_gba_gargoyle_enemy.gif",
  deathgoyle: "Ma_gba_gargoyle_enemy.gif",
  bael: "Ma_gba_bael_enemy.gif",
  "elder bael": "Ma_gba_bael_enemy.gif",
  "mauthe doog": "Ma_gba_mauthe_doog_enemy.gif",
  gwyllgi: "Ma_gba_mauthe_doog_enemy.gif",
  "draco zombie": "Ma_gba_draco_zombie_enemy.gif",
  "demon king": "Ma_gba_demon_king_enemy.gif",
};

const PORTRAIT_NAMES: Record<string, string> = {
  eirika: "eirika",
  ephraim: "ephraim",
  seth: "seth",
  franz: "franz",
  gilliam: "gilliam",
  moulder: "moulder",
  vanessa: "vanessa",
  ross: "ross",
  garcia: "garcia",
  neimi: "neimi",
  colm: "colm",
  artur: "artur",
  lute: "lute",
  natasha: "natasha",
  joshua: "joshua",
  forde: "forde",
  kyle: "kyle",
  tana: "tana",
  amelia: "amelia",
  innes: "innes",
  gerik: "gerik",
  tethys: "tethys",
  marisa: "marisa",
  larachel: "larachel",
  dozla: "dozla",
  saleh: "saleh",
  ewan: "ewan",
  cormag: "cormag",
  rennac: "rennac",
  duessel: "duessel",
  knoll: "knoll",
  myrrh: "myrrh",
  syrene: "syrene",
};

export function getClassSprite(unitClass: string): string {
  const normalized = unitClass.toLowerCase().trim();
  const sprite = CLASS_SPRITES[normalized];
  return sprite
    ? `/sprites/classes/${sprite}`
    : "/sprites/classes/Ma_gba_soldier_enemy.gif";
}

export function getPortraitUrl(name: string): string {
  const normalized = name.toLowerCase().trim();
  const portraitName = PORTRAIT_NAMES[normalized];
  if (portraitName) {
    return `/portraits/${portraitName}.png`;
  }
  return `/portraits/eirika.png`;
}

export function getChapterMapPath(
  chapterNum: number | string | undefined,
): string {
  if (chapterNum === undefined || chapterNum === null) {
    return "/sprites/maps/prologue.png";
  }

  const num =
    typeof chapterNum === "string"
      ? chapterNum.toLowerCase()
      : String(chapterNum);

  const mapFiles: Record<string, string> = {
    "0": "prologue.png",
    prologue: "prologue.png",
    p: "prologue.png",
    "1": "ch01.png",
    "2": "ch02.png",
    "3": "ch03.png",
    "4": "ch04.png",
    "5": "ch05.png",
    "5x": "ch05x.png",
    "6": "ch06.png",
    "7": "ch07.png",
    "8": "ch08.png",
    "9": "ch08.png",
    "9x": "ch09x.png",
    "10": "ch10-eirika.png",
    "10e": "ch10-eirika.png",
    "10p": "ch10-ephraim.png",
    "11": "ch11-eirika.png",
    "11e": "ch11-eirika.png",
    "11x": "ch11x-eirika.png",
    "12": "ch12-eirika.png",
    "12e": "ch12-eirika.png",
    "12x": "ch12x-eirika.png",
    "13": "ch13-eirika.png",
    "13e": "ch13-eirika.png",
    "13x": "ch13x-eirika.png",
    "14": "ch14-eirika.png",
    "14e": "ch14-eirika.png",
    "14x": "ch14x-eirika.png",
    "15": "ch15.png",
    "16": "ch15.png",
    "17": "ch15.png",
    "18": "ch15.png",
    "19": "ch15.png",
    "20": "ch15.png",
    final: "ch15.png",
    tower1: "tower-valni-1.png",
    tower2: "tower-valni-2.png",
    tower3: "tower-valni-3.png",
  };

  return `/sprites/maps/${mapFiles[num] || "prologue.png"}`;
}

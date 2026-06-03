/**
 * Fire Emblem: The Sacred Stones chapter data.
 * Defines the chapter tree structure with route branching.
 */

import type { ChapterNode, RouteType } from "../types/display";

export const SHARED_CHAPTERS: ChapterNode[] = [
  { id: "prologue", number: "P", title: "The Fall of Renais", route: "shared" },
  { id: "ch1", number: "1", title: "Escape!", route: "shared" },
  { id: "ch2", number: "2", title: "The Protected", route: "shared" },
  { id: "ch3", number: "3", title: "The Bandits of Borgo", route: "shared" },
  { id: "ch4", number: "4", title: "Ancient Horrors", route: "shared" },
  { id: "ch5", number: "5", title: "The Empire's Reach", route: "shared" },
  { id: "ch5x", number: "5x", title: "Unbroken Heart", route: "shared" },
  { id: "ch6", number: "6", title: "Victims of War", route: "shared" },
  { id: "ch7", number: "7", title: "Waterside Renvall", route: "shared" },
  { id: "ch8", number: "8", title: "It's a Trap!", route: "shared" },
];

export const EIRIKA_CHAPTERS: ChapterNode[] = [
  { id: "ch9e", number: "9", title: "Distant Blade", route: "eirika" },
  { id: "ch10e", number: "10", title: "Revolt at Carcino", route: "eirika" },
  { id: "ch11e", number: "11", title: "Creeping Darkness", route: "eirika" },
  { id: "ch12e", number: "12", title: "Village of Silence", route: "eirika" },
  { id: "ch13e", number: "13", title: "Hamill Canyon", route: "eirika" },
  { id: "ch14e", number: "14", title: "Queen of White Dunes", route: "eirika" },
  { id: "ch15e", number: "15", title: "Scorched Sand", route: "eirika" },
];

export const EPHRAIM_CHAPTERS: ChapterNode[] = [
  { id: "ch9p", number: "9", title: "Fort Rigwald", route: "ephraim" },
  { id: "ch10p", number: "10", title: "Turning Traitor", route: "ephraim" },
  { id: "ch11p", number: "11", title: "Phantom Ship", route: "ephraim" },
  { id: "ch12p", number: "12", title: "Landing at Taizel", route: "ephraim" },
  { id: "ch13p", number: "13", title: "Fluorspar's Oath", route: "ephraim" },
  { id: "ch14p", number: "14", title: "Father and Son", route: "ephraim" },
  { id: "ch15p", number: "15", title: "Scorched Sand", route: "ephraim" },
];

export const FINAL_CHAPTERS: ChapterNode[] = [
  { id: "ch16", number: "16", title: "Ruled by Madness", route: "shared" },
  { id: "ch17", number: "17", title: "River of Regrets", route: "shared" },
  { id: "ch18", number: "18", title: "Two Faces of Evil", route: "shared" },
  { id: "ch19", number: "19", title: "Last Hope", route: "shared" },
  { id: "ch20", number: "20", title: "Darkling Woods", route: "shared" },
  { id: "final", number: "F", title: "Sacred Stones", route: "shared" },
];

export function getAllChapters(route: RouteType | null): ChapterNode[] {
  if (route === "eirika") {
    return [...SHARED_CHAPTERS, ...EIRIKA_CHAPTERS, ...FINAL_CHAPTERS];
  }
  if (route === "ephraim") {
    return [...SHARED_CHAPTERS, ...EPHRAIM_CHAPTERS, ...FINAL_CHAPTERS];
  }
  return SHARED_CHAPTERS;
}

export function parseChapterNumber(chapterStr: string | undefined): {
  number: string;
  route: RouteType | null;
} {
  if (!chapterStr) {
    return { number: "P", route: null };
  }

  const normalized = chapterStr.toLowerCase().trim();

  if (normalized === "prologue" || normalized === "p" || normalized === "0") {
    return { number: "P", route: null };
  }

  if (normalized === "final" || normalized === "f" || normalized === "21") {
    return { number: "F", route: null };
  }

  const match = normalized.match(/^(\d+)(x?)([ep]?)$/);
  if (match) {
    const [, num, x, routeSuffix] = match;
    const chapterNum = parseInt(num, 10);

    let route: RouteType | null = null;
    if (routeSuffix === "e") route = "eirika";
    if (routeSuffix === "p") route = "ephraim";

    if (chapterNum >= 9 && chapterNum <= 15 && !routeSuffix) {
      route = "eirika";
    }

    return {
      number: x ? `${num}x` : num,
      route: chapterNum <= 8 ? null : route,
    };
  }

  return { number: chapterStr, route: null };
}

export function getChapterIndex(
  chapterNum: string,
  route: RouteType | null,
): number {
  const chapters = getAllChapters(route);
  const normalized = chapterNum.toLowerCase().replace(/^0+/, "");

  return chapters.findIndex((ch) => {
    const chNum = ch.number.toLowerCase();
    return chNum === normalized || chNum === chapterNum.toLowerCase();
  });
}

export function isRouteChapter(chapterNum: string): boolean {
  const num = parseInt(chapterNum, 10);
  return num >= 9 && num <= 15;
}

export const ROUTE_SPLIT_CHAPTER = "8";

export function getChapterDisplayName(chapterNum: string): string {
  const normalized = chapterNum.toLowerCase().trim();

  if (normalized === "p" || normalized === "0" || normalized === "prologue") {
    return "Prologue";
  }

  if (normalized === "f" || normalized === "21" || normalized === "final") {
    return "Final";
  }

  if (normalized.endsWith("x")) {
    return `Chapter ${normalized.replace("x", "x")}`;
  }

  return `Chapter ${chapterNum}`;
}

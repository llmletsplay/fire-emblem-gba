import { useState, useRef, useCallback } from "react";
import type { ThoughtEntry } from "../types/display";
import { transformThought } from "../utils/transformers";

const MAX_THOUGHTS = 20;

export function useThoughts() {
  const [thoughts, setThoughts] = useState<ThoughtEntry[]>([]);
  const lastThoughtRef = useRef<string>("");

  const addThought = useCallback((rawThought: string, screenshot?: string) => {
    if (rawThought === lastThoughtRef.current) {
      return;
    }

    lastThoughtRef.current = rawThought;
    const entry = transformThought(rawThought, screenshot);

    setThoughts((prev) => [...prev, entry].slice(-MAX_THOUGHTS));
  }, []);

  const clearThoughts = useCallback(() => {
    setThoughts([]);
    lastThoughtRef.current = "";
  }, []);

  return {
    thoughts,
    addThought,
    clearThoughts,
  };
}

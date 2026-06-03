import type { ClassSpriteProps } from "./types";
import "./ClassSprite.css";

export function ClassSprite({ src, alt, size = "md" }: ClassSpriteProps) {
  return (
    <img
      src={src}
      alt={alt}
      className={`class-sprite class-sprite--${size}`}
      loading="lazy"
    />
  );
}

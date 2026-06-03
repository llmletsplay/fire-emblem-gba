import "./ClassSprite.css";

interface ClassSpriteProps {
  src: string;
  alt: string;
  size?: "sm" | "md" | "lg";
}

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

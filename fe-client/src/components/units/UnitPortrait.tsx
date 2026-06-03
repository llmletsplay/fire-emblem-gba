import { useState } from "react";
import "./UnitPortrait.css";

interface UnitPortraitProps {
  src: string;
  name: string;
  size?: "sm" | "md" | "lg";
}

export function UnitPortrait({ src, name, size = "md" }: UnitPortraitProps) {
  const [imgError, setImgError] = useState(false);

  return (
    <div className={`unit-portrait unit-portrait--${size}`}>
      <img
        src={imgError ? "/portraits/eirika.png" : src}
        alt={name}
        className="unit-portrait__img"
        onError={() => setImgError(true)}
        loading="lazy"
      />
    </div>
  );
}

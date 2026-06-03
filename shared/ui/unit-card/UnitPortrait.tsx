import { useState } from "react";
import type { UnitPortraitProps } from "./types";
import "./UnitPortrait.css";

const FALLBACK_PORTRAIT = "/portraits/eirika.png";

export function UnitPortrait({ src, name, size = "md" }: UnitPortraitProps) {
  const [imgError, setImgError] = useState(false);

  return (
    <div className={`unit-portrait unit-portrait--${size}`}>
      <img
        src={imgError ? FALLBACK_PORTRAIT : src}
        alt={name}
        className="unit-portrait__img"
        onError={() => setImgError(true)}
        loading="lazy"
      />
    </div>
  );
}

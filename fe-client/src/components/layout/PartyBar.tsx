import { useRef, useEffect, useState } from "react";
import type { PartyBarProps } from "../../types/display";
import { UnitCard } from "../units/UnitCard";
import "./PartyBar.css";

const SCROLL_SPEED = 50;
const PAUSE_DURATION = 3000;

export function PartyBar({ units }: PartyBarProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  const playerUnits = units.filter(
    (u) => u.affiliation === "player" || u.affiliation === "ally",
  );

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const checkOverflow = () => {
      setIsOverflowing(container.scrollWidth > container.clientWidth);
    };

    checkOverflow();
    window.addEventListener("resize", checkOverflow);
    return () => window.removeEventListener("resize", checkOverflow);
  }, [playerUnits.length]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || !isOverflowing) return;

    let animationId: number;
    let direction = 1;
    let isPaused = false;
    let pauseTimeout: ReturnType<typeof setTimeout>;

    const animate = () => {
      if (isPaused) {
        animationId = requestAnimationFrame(animate);
        return;
      }

      const maxScroll = container.scrollWidth - container.clientWidth;
      const currentScroll = container.scrollLeft;

      if (direction === 1 && currentScroll >= maxScroll) {
        isPaused = true;
        pauseTimeout = setTimeout(() => {
          direction = -1;
          isPaused = false;
        }, PAUSE_DURATION);
      } else if (direction === -1 && currentScroll <= 0) {
        isPaused = true;
        pauseTimeout = setTimeout(() => {
          direction = 1;
          isPaused = false;
        }, PAUSE_DURATION);
      } else {
        container.scrollLeft += direction * (SCROLL_SPEED / 60);
      }

      animationId = requestAnimationFrame(animate);
    };

    const startTimeout = setTimeout(() => {
      animationId = requestAnimationFrame(animate);
    }, PAUSE_DURATION);

    return () => {
      cancelAnimationFrame(animationId);
      clearTimeout(startTimeout);
      clearTimeout(pauseTimeout);
    };
  }, [isOverflowing]);

  return (
    <div className="party-bar">
      <div className="party-bar__main">
        <div className="party-bar__header">
          <h2 className="party-bar__title">Party Members</h2>
          <span className="party-bar__count">{playerUnits.length} units</span>
        </div>

        <div className="party-bar__scroll" ref={scrollRef}>
          {playerUnits.length > 0 ? (
            playerUnits.map((unit) => <UnitCard key={unit.id} unit={unit} />)
          ) : (
            <div className="party-bar__empty">No units deployed</div>
          )}
        </div>
      </div>

      <div className="party-bar__sponsor">
        <div className="party-bar__sponsor-header">
          <span className="party-bar__sponsor-label">Presented By</span>
          <a
            href="https://phantasy.bot"
            target="_blank"
            rel="noopener noreferrer"
            className="party-bar__sponsor-link"
          >
            phantasy.bot
          </a>
        </div>
        <div className="party-bar__sponsor-card">
          <div className="party-bar__sponsor-portrait">
            <img
              src="/portraits/phantasy.png"
              alt="Phantasy"
              className="party-bar__sponsor-portrait-img"
            />
          </div>
          <div className="party-bar__sponsor-info">
            <div className="party-bar__sponsor-header">
              <span className="party-bar__sponsor-name">Phantasy</span>
              <span className="party-bar__sponsor-level">Lv.∞</span>
            </div>
            <div className="party-bar__sponsor-hp">
              <div className="party-bar__sponsor-hp-track">
                <div className="party-bar__sponsor-hp-fill" />
              </div>
              <span className="party-bar__sponsor-hp-text">∞/∞</span>
            </div>
            <div className="party-bar__sponsor-class">
              <img
                src="/sprites/classes/sponsor.gif"
                alt="Sponsor"
                className="party-bar__sponsor-sprite"
              />
              <span className="party-bar__sponsor-class-name">Sponsor</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

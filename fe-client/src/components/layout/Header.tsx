import type { HeaderProps } from "../../types/display";
import { BrandingBlock } from "../header/BrandingBlock";
import { ChapterTree } from "../header/ChapterTree";
import { ActionsCounter } from "../header/ActionsCounter";
import "./Header.css";

export function Header({
  modelName,
  chapterTree,
  actionCount,
  tokenCount,
  inputTokens,
}: HeaderProps) {
  return (
    <header className="header">
      <div className="header__left">
        <BrandingBlock />
        <div className="header__model">
          <span className="header__model-name">{modelName || "Claude"}</span>
        </div>
      </div>

      <div className="header__center">
        <ChapterTree state={chapterTree} />
      </div>

      <div className="header__right">
        <ActionsCounter
          count={actionCount}
          tokenCount={tokenCount}
          inputTokens={inputTokens}
        />
      </div>
    </header>
  );
}

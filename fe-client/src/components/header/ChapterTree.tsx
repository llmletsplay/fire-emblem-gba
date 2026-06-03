import type { ChapterTreeProps } from "../../types/display";
import {
  SHARED_CHAPTERS,
  EIRIKA_CHAPTERS,
  EPHRAIM_CHAPTERS,
  FINAL_CHAPTERS,
} from "../../utils/chapterData";
import "./ChapterTree.css";

export function ChapterTree({ state }: ChapterTreeProps) {
  const { currentChapter, currentRoute, completedChapters } = state;

  const getNodeStatus = (chapterId: string) => {
    if (completedChapters.includes(chapterId)) return "completed";
    if (chapterId === currentChapter) return "current";
    return "future";
  };

  const showRouteBranch =
    currentRoute !== null ||
    completedChapters.some(
      (id) =>
        EIRIKA_CHAPTERS.some((ch) => ch.id === id) ||
        EPHRAIM_CHAPTERS.some((ch) => ch.id === id),
    );

  return (
    <div className="chapter-tree">
      <div className="chapter-tree__track">
        {/* Shared chapters (Prologue through Ch8) */}
        <div className="chapter-tree__section chapter-tree__section--shared">
          {SHARED_CHAPTERS.map((chapter, index) => (
            <div key={chapter.id} className="chapter-tree__node-wrapper">
              <div
                className={`chapter-tree__node chapter-tree__node--${getNodeStatus(chapter.id)}`}
                title={`${chapter.number}: ${chapter.title}`}
              >
                <span className="chapter-tree__node-label">
                  {chapter.number}
                </span>
              </div>
              {index < SHARED_CHAPTERS.length - 1 && (
                <div
                  className={`chapter-tree__connector chapter-tree__connector--${
                    completedChapters.includes(chapter.id)
                      ? "completed"
                      : "future"
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Route branch visualization */}
        {showRouteBranch && (
          <div className="chapter-tree__branch">
            <div className="chapter-tree__branch-split">
              <div className="chapter-tree__branch-line chapter-tree__branch-line--top" />
              <div className="chapter-tree__branch-line chapter-tree__branch-line--bottom" />
            </div>

            {/* Eirika route */}
            <div
              className={`chapter-tree__route chapter-tree__route--eirika ${currentRoute === "eirika" ? "active" : ""}`}
            >
              <span className="chapter-tree__route-label">Eirika</span>
              <div className="chapter-tree__route-nodes">
                {EIRIKA_CHAPTERS.slice(0, 4).map((chapter) => (
                  <div
                    key={chapter.id}
                    className={`chapter-tree__node chapter-tree__node--sm chapter-tree__node--${getNodeStatus(chapter.id)}`}
                    title={`${chapter.number}: ${chapter.title}`}
                  >
                    <span className="chapter-tree__node-label">
                      {chapter.number}
                    </span>
                  </div>
                ))}
                <span className="chapter-tree__ellipsis">...</span>
              </div>
            </div>

            {/* Ephraim route */}
            <div
              className={`chapter-tree__route chapter-tree__route--ephraim ${currentRoute === "ephraim" ? "active" : ""}`}
            >
              <span className="chapter-tree__route-label">Ephraim</span>
              <div className="chapter-tree__route-nodes">
                {EPHRAIM_CHAPTERS.slice(0, 4).map((chapter) => (
                  <div
                    key={chapter.id}
                    className={`chapter-tree__node chapter-tree__node--sm chapter-tree__node--${getNodeStatus(chapter.id)}`}
                    title={`${chapter.number}: ${chapter.title}`}
                  >
                    <span className="chapter-tree__node-label">
                      {chapter.number}
                    </span>
                  </div>
                ))}
                <span className="chapter-tree__ellipsis">...</span>
              </div>
            </div>
          </div>
        )}

        {/* Final chapters (reunited) */}
        {showRouteBranch && (
          <div className="chapter-tree__section chapter-tree__section--final">
            <div className="chapter-tree__merge-line" />
            {FINAL_CHAPTERS.slice(0, 3).map((chapter) => (
              <div key={chapter.id} className="chapter-tree__node-wrapper">
                <div
                  className={`chapter-tree__node chapter-tree__node--${getNodeStatus(chapter.id)}`}
                  title={`${chapter.number}: ${chapter.title}`}
                >
                  <span className="chapter-tree__node-label">
                    {chapter.number}
                  </span>
                </div>
              </div>
            ))}
            <span className="chapter-tree__ellipsis">...</span>
          </div>
        )}
      </div>
    </div>
  );
}

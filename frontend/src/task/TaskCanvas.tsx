import { keyLabel } from "./keymap";
import type { BlockProgress } from "./sessionRunner";
import type { EngineSnapshot, FeedbackKind } from "./trialEngine";

const CONTAINER_SIZE = 96;
const GAP = 48;
const CROSS_ARM = 28; // each side of center -> 56px total
const BOX_SIZE = 64;
const STROKE = 6;
const BLACK = "#000000";

function StimulusGlyph({ showBox }: { showBox: boolean }): JSX.Element {
  const center = CONTAINER_SIZE / 2;
  return (
    <svg width={CONTAINER_SIZE} height={CONTAINER_SIZE} viewBox={`0 0 ${CONTAINER_SIZE} ${CONTAINER_SIZE}`} aria-hidden="true">
      {showBox ? (
        <rect
          x={center - BOX_SIZE / 2}
          y={center - BOX_SIZE / 2}
          width={BOX_SIZE}
          height={BOX_SIZE}
          fill="none"
          stroke={BLACK}
          strokeWidth={STROKE}
        />
      ) : (
        <>
          <line x1={center} y1={center - CROSS_ARM} x2={center} y2={center + CROSS_ARM} stroke={BLACK} strokeWidth={STROKE} />
          <line x1={center - CROSS_ARM} y1={center} x2={center + CROSS_ARM} y2={center} stroke={BLACK} strokeWidth={STROKE} />
        </>
      )}
    </svg>
  );
}

const FEEDBACK_TEXT: Record<FeedbackKind, string> = {
  incorrect: "✗",
  timeout: "Too slow",
  too_soon: "Too soon!",
};

interface TaskCanvasProps {
  nPositions: number;
  snapshot: EngineSnapshot | null;
  showProgress: boolean;
  progress: BlockProgress | null;
}

/**
 * §5.1 trial canvas: white background, N 96x96px stimulus containers with
 * 48px gaps, a feedback zone 64px below, and a thin progress bar at the
 * bottom of the viewport. Used for practice/test blocks and (FR-33) preview.
 */
export default function TaskCanvas({ nPositions, snapshot, showProgress, progress }: TaskCanvasProps): JSX.Element {
  const boxPosition = snapshot?.boxPosition ?? null;
  const feedback = snapshot?.feedback ?? null;
  const pct = progress && progress.totalSlots > 0 ? (progress.completedSlots / progress.totalSlots) * 100 : 0;

  return (
    <div style={{ position: "fixed", inset: 0, backgroundColor: "#FFFFFF" }}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "flex", gap: `${GAP}px` }}>
          {Array.from({ length: nPositions }, (_, i) => (
            <StimulusGlyph key={i} showBox={boxPosition === i} />
          ))}
        </div>
        <div style={{ marginTop: "64px", height: "56px", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {feedback === "incorrect" ? (
            <span style={{ color: "#CC0000", fontSize: "48px", lineHeight: 1 }}>{FEEDBACK_TEXT.incorrect}</span>
          ) : feedback ? (
            <span style={{ color: BLACK, fontSize: "32px", lineHeight: 1 }}>{FEEDBACK_TEXT[feedback]}</span>
          ) : null}
        </div>
      </div>
      {showProgress && (
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "4px", backgroundColor: "#E5E7EB" }}>
          <div style={{ height: "100%", width: `${pct}%`, backgroundColor: "#9CA3AF" }} />
        </div>
      )}
    </div>
  );
}

/** Instructions-screen diagram: the same N containers (all crosses) with each
 * key's display label below it, per §3.2 step 6 ("a diagram of the crosses,
 * the key mapping"). */
export function KeyMappingDiagram({ keyMap }: { keyMap: string[] }): JSX.Element {
  return (
    <div style={{ display: "flex", gap: `${GAP}px`, justifyContent: "center" }}>
      {keyMap.map((code) => (
        <div key={code} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
          <StimulusGlyph showBox={false} />
          <span className="text-lg font-semibold text-gray-700">{keyLabel(code)}</span>
        </div>
      ))}
    </div>
  );
}

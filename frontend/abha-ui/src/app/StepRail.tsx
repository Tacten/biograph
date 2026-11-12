import type { StepDef } from "../domain/stepContract";
import type { Known } from "../domain/known";

type State = "done" | "current" | "skipped" | "todo";

/** Steps the person will actually see: skipped ones stay listed (struck through) so the rail does not jump. */
export function StepRail({ steps, currentId, known, label, visited }: { steps: StepDef[]; currentId: string; known: Known; label: string; visited?: ReadonlySet<string> }) {
  const currentIndex = steps.findIndex((s) => s.id === currentId);
  let shown = 0;
  return (
    <ol className="rail card" aria-label={label}>
      {steps.map((step, i) => {
        // A step the person actually went through is done, even if what it collected now makes it "not needed".
        const skipped = (step.skipWhen?.(known) ?? false) && !visited?.has(step.id) && i !== currentIndex;
        const state: State = skipped ? "skipped" : i < currentIndex ? "done" : i === currentIndex ? "current" : "todo";
        if (!skipped) shown += 1;
        return (
          <li key={step.id} className="rail-item" data-state={state} aria-current={state === "current" ? "step" : undefined}>
            <span className="rail-mark" aria-hidden="true">{state === "done" ? "✓" : skipped ? "–" : shown}</span>
            <span>
              {step.title}
              {skipped && <span className="sr-only"> (not needed)</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

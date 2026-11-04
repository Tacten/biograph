import type { FactKey, Known } from "./known";

/**
 * Every screen of a journey declares what it asks the person for, what the system learns on it, and when it does
 * not appear at all. A test walks each journey and fails if any step asks for something already known.
 */
export interface StepDef {
  id: string;
  title: string;
  /** Facts this step asks the person to type, choose or confirm. */
  collects: FactKey[];
  /** Facts this step is forbidden to ask (they are asked elsewhere, or must never be asked here). */
  forbidden?: FactKey[];
  /** Facts the system obtains on this step from ABDM's reply, so later steps already know them. */
  learns?: FactKey[];
  /** True when the step must not appear for this state (for example, the mobile is the Aadhaar-linked one). */
  skipWhen?: (known: Known) => boolean;
}

export interface Violation {
  step: string;
  fact: FactKey;
  reason: "asked-again" | "forbidden";
}

const PLACEHOLDER = "x";

function knownFromKeys(keys: Set<FactKey>): Known {
  const k: Record<string, unknown> = {};
  for (const key of keys) k[key] = key === "patient" ? { name: PLACEHOLDER, patient_name: PLACEHOLDER } : PLACEHOLDER;
  return k as Known;
}

/** Walk a journey in order, remembering what each step collected or learned. */
export function findRepeatedQuestions(steps: StepDef[], seed: FactKey[] = []): Violation[] {
  const known = new Set<FactKey>(seed);
  const violations: Violation[] = [];
  for (const step of steps) {
    if (step.skipWhen?.(knownFromKeys(known))) continue;
    for (const fact of step.collects) {
      if (step.forbidden?.includes(fact)) violations.push({ step: step.id, fact, reason: "forbidden" });
      else if (known.has(fact)) violations.push({ step: step.id, fact, reason: "asked-again" });
      known.add(fact);
    }
    for (const fact of step.learns ?? []) known.add(fact);
  }
  return violations;
}

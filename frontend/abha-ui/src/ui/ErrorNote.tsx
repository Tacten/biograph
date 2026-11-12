import type { ReactNode } from "react";

/** What went wrong, in the words the server or ABDM used. Announced to screen readers when it appears. */
export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <div className="note note-bad" role="alert">
      {children}
    </div>
  );
}

export function InfoNote({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "ok" | "warn" }) {
  return (
    <div className={`note note-${tone}`} role="status">
      {children}
    </div>
  );
}

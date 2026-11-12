import { useId, type InputHTMLAttributes, type ReactNode } from "react";

export function Field({ label, hint, error, ...input }: { label: string; hint?: ReactNode; error?: string | null } & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} aria-invalid={error ? true : undefined} aria-describedby={`${id}-d`} {...input} />
      <div id={`${id}-d`} className={error ? "field-error" : "field-hint"}>
        {error || hint}
      </div>
    </div>
  );
}

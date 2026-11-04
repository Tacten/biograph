import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";

const LENGTH = 6;

/**
 * Six boxes, one digit each. Paste fills them all, Backspace steps back, and the code is handed over once, the
 * moment the sixth digit is in. To clear after a wrong code, give the component a new `key`.
 */
export function OtpInput({ onComplete, disabled = false, invalid = false, label = "One-time password" }: { onComplete: (code: string) => void; disabled?: boolean; invalid?: boolean; label?: string }) {
  const [digits, setDigits] = useState<string[]>(Array(LENGTH).fill(""));
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const sent = useRef(false);

  useEffect(() => {
    refs.current[0]?.focus();
  }, []);

  function commit(next: string[]) {
    setDigits(next);
    const code = next.join("");
    if (code.length === LENGTH && !sent.current) {
      sent.current = true;
      onComplete(code);
    }
  }

  function fill(from: number, text: string) {
    const clean = text.replace(/\D/g, "");
    if (!clean) return;
    const next = [...digits];
    let i = from;
    for (const ch of clean) {
      if (i >= LENGTH) break;
      next[i++] = ch;
    }
    refs.current[Math.min(i, LENGTH - 1)]?.focus();
    commit(next);
  }

  function onKeyDown(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace") {
      e.preventDefault();
      const next = [...digits];
      if (next[i]) next[i] = "";
      else if (i > 0) {
        next[i - 1] = "";
        refs.current[i - 1]?.focus();
      }
      sent.current = false;
      setDigits(next);
    } else if (e.key === "ArrowLeft" && i > 0) refs.current[i - 1]?.focus();
    else if (e.key === "ArrowRight" && i < LENGTH - 1) refs.current[i + 1]?.focus();
  }

  function onPaste(i: number, e: ClipboardEvent<HTMLInputElement>) {
    e.preventDefault();
    fill(i, e.clipboardData.getData("text"));
  }

  return (
    <div className="otp" role="group" aria-label={label}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          className="otp-box"
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          maxLength={LENGTH}
          aria-label={`Digit ${i + 1} of ${LENGTH}`}
          aria-invalid={invalid || undefined}
          disabled={disabled}
          value={d}
          onChange={(e) => fill(i, e.target.value)}
          onKeyDown={(e) => onKeyDown(i, e)}
          onPaste={(e) => onPaste(i, e)}
          onFocus={(e) => e.target.select()}
        />
      ))}
    </div>
  );
}

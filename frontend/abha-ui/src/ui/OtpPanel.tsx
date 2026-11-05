import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError } from "../api/client";
import { ErrorNote, InfoNote } from "./ErrorNote";
import { OtpInput } from "./OtpInput";
import { useResend } from "./useResend";

const messageOf = (e: unknown, fallback: string) => (e instanceof ApiError || e instanceof Error ? e.message : fallback);

/**
 * The OTP screen every journey shares: six boxes that verify on the sixth digit, a Resend that is locked for 60 s
 * and can be used twice, ABDM's own reason when a code is refused, and the boxes cleared for another try.
 *
 * `verify` resolves when the code is accepted, and throws (any Error) with the words to show when it is not.
 * `send` is optional: pass it when this screen is what sends the first OTP; otherwise the OTP was sent before.
 */
export function OtpPanel({ heading, lede, label, verify, resend, send, back, children }: {
  heading: string;
  lede: string;
  label: string;
  verify: (code: string) => Promise<void>;
  resend: () => Promise<void>;
  send?: () => Promise<void>;
  back?: { label: string; onClick: () => void };
  children?: ReactNode;
}) {
  const timer = useResend();
  const [round, setRound] = useState(0); // a new round gives the boxes a new key, which clears them
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // React's dev double-run must not send, or count, the first OTP twice
    started.current = true;
    if (!send) return timer.markSent();
    setBusy(true);
    send()
      .then(() => timer.markSent())
      .catch((e: unknown) => setError(messageOf(e, "Could not send the OTP.")))
      .finally(() => setBusy(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function check(code: string) {
    setBusy(true);
    setError("");
    try {
      await verify(code);
    } catch (e) {
      setError(messageOf(e, "Could not verify the OTP."));
      setRound((r) => r + 1);
    } finally {
      setBusy(false);
    }
  }

  async function again() {
    setError("");
    setNote("");
    try {
      await resend();
      timer.markSent();
      setRound((r) => r + 1);
      setNote("A new OTP has been sent.");
    } catch (e) {
      setError(messageOf(e, "Could not send the OTP again."));
    }
  }

  return (
    <div>
      <h2 id="step-title">{heading}</h2>
      <p className="lede">{lede}</p>
      {children}
      <OtpInput key={round} onComplete={check} disabled={busy} invalid={Boolean(error)} label={label} />
      {busy && <p className="muted" role="status">Working…</p>}
      <ErrorNote>{error}</ErrorNote>
      {note && <InfoNote tone="ok">{note}</InfoNote>}
      <div className="actions">
        <button type="button" className="btn" onClick={again} disabled={!timer.canResend || busy}>
          {timer.secondsLeft > 0 ? `Resend OTP in ${timer.secondsLeft}s` : timer.resendsLeft === 0 ? "No resends left" : "Resend OTP"}
        </button>
        {back && (
          <button type="button" className="btn btn-quiet" onClick={back.onClick}>
            {back.label}
          </button>
        )}
      </div>
      <p className="muted small">{timer.resendsLeft} resend{timer.resendsLeft === 1 ? "" : "s"} left.</p>
    </div>
  );
}

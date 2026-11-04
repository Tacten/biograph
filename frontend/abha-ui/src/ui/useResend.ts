import { useCallback, useEffect, useState } from "react";

/** After each send the Resend button is locked for `lockSeconds`, and it can be used `maxResends` times (CRT_ABHA_106). */
export function useResend(lockSeconds = 60, maxResends = 2) {
  const [sends, setSends] = useState(0);
  const [lockedUntil, setLockedUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (lockedUntil <= Date.now()) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [lockedUntil]);

  const markSent = useCallback(() => {
    setSends((n) => n + 1);
    setLockedUntil(Date.now() + lockSeconds * 1000);
    setNow(Date.now());
  }, [lockSeconds]);

  const secondsLeft = Math.max(0, Math.ceil((lockedUntil - now) / 1000));
  const resendsUsed = Math.max(0, sends - 1);
  return {
    markSent,
    secondsLeft,
    resendsLeft: Math.max(0, maxResends - resendsUsed),
    canResend: sends > 0 && secondsLeft === 0 && resendsUsed < maxResends,
  };
}

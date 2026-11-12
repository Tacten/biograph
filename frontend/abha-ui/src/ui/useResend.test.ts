import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useResend } from "./useResend";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useResend", () => {
  it("locks Resend for 60 s after each send and allows two resends in all", () => {
    const { result } = renderHook(() => useResend());
    expect(result.current.canResend).toBe(false); // nothing sent yet

    act(() => result.current.markSent());
    expect(result.current.secondsLeft).toBe(60);
    expect(result.current.canResend).toBe(false);

    act(() => { vi.advanceTimersByTime(59_000); });
    expect(result.current.canResend).toBe(false);
    act(() => { vi.advanceTimersByTime(1_000); });
    expect(result.current.canResend).toBe(true);
    expect(result.current.resendsLeft).toBe(2);

    act(() => result.current.markSent()); // first resend
    expect(result.current.canResend).toBe(false);
    expect(result.current.resendsLeft).toBe(1);
    act(() => { vi.advanceTimersByTime(60_000); });
    expect(result.current.canResend).toBe(true);

    act(() => result.current.markSent()); // second resend
    act(() => { vi.advanceTimersByTime(120_000); });
    expect(result.current.resendsLeft).toBe(0);
    expect(result.current.canResend).toBe(false);
  });
});

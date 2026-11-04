import { afterEach, describe, expect, it, vi } from "vitest";
import { defaultRd, RdServiceError } from "./rdService";

afterEach(() => vi.unstubAllGlobals());

const xml = (errCode: string, errInfo = "") => `<PidData><Resp errCode="${errCode}" errInfo="${errInfo}" fCount="1"/><Data type="X">QUJD</Data></PidData>`;

function device(port: number, capture: string) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (!url.includes(`:${port}`)) throw new TypeError("refused");
    if (init?.method === "RDSERVICE") return new Response("<RDService status='READY'/>");
    return new Response(capture);
  });
}

describe("RD Service capture", () => {
  it("finds the service on a port in the vendor range, captures, and returns the PID block as received", async () => {
    const f = device(11105, xml("0"));
    vi.stubGlobal("fetch", f);
    expect(await defaultRd.capture()).toBe(xml("0"));
    const capture = f.mock.calls.find(([, i]) => (i as RequestInit | undefined)?.method === "CAPTURE")!;
    expect(String(capture[0])).toBe("http://127.0.0.1:11105/rd/capture");
    expect(String((capture[1] as RequestInit).body)).toContain("<PidOptions");
  });

  it("says what the device reported when the scan fails", async () => {
    vi.stubGlobal("fetch", device(11100, xml("700", "Capture timed out")));
    await expect(defaultRd.capture()).rejects.toThrow("The device reported: Capture timed out");
  });

  it("says no device was found when nothing answers", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("refused"); }));
    await expect(defaultRd.capture()).rejects.toBeInstanceOf(RdServiceError);
    await expect(defaultRd.capture()).rejects.toThrow(/No fingerprint device was found/);
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { toJpegBase64 } from "./image";

afterEach(() => vi.unstubAllGlobals());

/** A canvas whose JPEG size depends on the picture's area and the quality, like a real one. */
function stubBrowser(bitmapSize: number, bytesPerPixelAtFullQuality: number) {
  vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: bitmapSize, height: bitmapSize })));
  const made: { w: number; h: number; q: number[] }[] = [];
  vi.spyOn(document, "createElement").mockImplementation(((tag: string) => {
    if (tag !== "canvas") return document.createElementNS("http://www.w3.org/1999/xhtml", tag);
    const rec = { w: 0, h: 0, q: [] as number[] };
    made.push(rec);
    const c = {
      get width() { return rec.w; }, set width(v: number) { rec.w = v; },
      get height() { return rec.h; }, set height(v: number) { rec.h = v; },
      getContext: () => ({ fillRect() {}, drawImage() {}, set fillStyle(_v: string) {} }),
      toBlob(cb: (b: Blob | null) => void, _type: string, q: number) {
        rec.q.push(q);
        cb(new Blob([new Uint8Array(Math.round(rec.w * rec.h * bytesPerPixelAtFullQuality * q))], { type: "image/jpeg" }));
      },
    };
    return c as unknown as HTMLCanvasElement;
  }) as typeof document.createElement);
  return made;
}

describe("toJpegBase64", () => {
  it("returns the picture as plain base64 when it already fits", async () => {
    stubBrowser(100, 0.5);
    const b64 = await toJpegBase64(new File(["x"], "p.jpg", { type: "image/jpeg" }));
    expect(b64).not.toContain("data:");
    expect(atob(b64).length).toBeLessThanOrEqual(150 * 1024);
  });

  it("shrinks a big picture, lowering quality then size, until it is at most 150 KB", async () => {
    const made = stubBrowser(4000, 0.2);
    const b64 = await toJpegBase64(new File(["x"], "p.jpg", { type: "image/jpeg" }));
    expect(atob(b64).length).toBeLessThanOrEqual(150 * 1024);
    expect(made.length).toBeGreaterThan(1); // it had to try smaller sizes
    expect(Math.max(...made.map((m) => Math.max(m.w, m.h)))).toBeLessThanOrEqual(1400);
  });

  it("gives up with a plain message when it cannot get under the limit", async () => {
    stubBrowser(4000, 50);
    await expect(toJpegBase64(new File(["x"], "p.jpg", { type: "image/jpeg" }))).rejects.toThrow(/150 KB/);
  });

  it("says so when the file is not a picture the browser can read", async () => {
    vi.stubGlobal("createImageBitmap", vi.fn(async () => { throw new Error("bad"); }));
    await expect(toJpegBase64(new File(["x"], "p.pdf", { type: "application/pdf" }))).rejects.toThrow(/not a picture/);
  });
});

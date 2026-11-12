const MAX_EDGE = 1400;
const QUALITIES = [0.85, 0.7, 0.55, 0.4];

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onerror = () => reject(new Error("Could not read the photograph."));
    r.onload = () => {
      const url = String(r.result);
      resolve(url.slice(url.indexOf(",") + 1));
    };
    r.readAsDataURL(blob);
  });
}

/**
 * A photograph as a JPEG of at most `maxBytes` (ABDM rejects licence photos over 150 KB), as plain base64.
 * Shrinks the picture and lowers the quality until it fits. Done in the browser; nothing is uploaded or stored.
 */
export async function toJpegBase64(file: File, maxBytes = 150 * 1024): Promise<string> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("That file is not a picture this browser can read. Choose a PNG or JPG photograph.");
  }
  let scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
  for (let round = 0; round < 8; round++) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("This browser cannot prepare the photograph.");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    for (const q of QUALITIES) {
      const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, "image/jpeg", q));
      if (blob && blob.size <= maxBytes) return blobToBase64(blob);
    }
    scale *= 0.75;
  }
  throw new Error("The photograph could not be made small enough for ABDM (150 KB). Try a closer, plainer photograph.");
}

/**
 * Fingerprint capture through the device's RD Service, a small web service the device vendor installs on the desk PC
 * (UIDAI's Registered Device specification). The browser asks it on 127.0.0.1; it returns the signed, encrypted PID
 * block. The block is handed on and never stored or logged here.
 *
 * UNTESTED against a real device or ABDM: the discovery ports, the PidOptions values and what ABDM expects inside
 * `fingerPrintAuthPid` follow the RD Service specification and the SOP, and need confirming with a device.
 */
export class RdServiceError extends Error {}

export interface RdClient {
  /** Capture one fingerprint and return the device's PID block (an XML string). Throws RdServiceError with a reason. */
  capture(): Promise<string>;
}

const PORTS = Array.from({ length: 21 }, (_, i) => 11100 + i);

async function withTimeout(url: string, init: RequestInit, ms: number): Promise<Response> {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: c.signal });
  } finally {
    clearTimeout(t);
  }
}

async function findPort(): Promise<number> {
  for (const port of PORTS) {
    try {
      const res = await withTimeout(`http://127.0.0.1:${port}/`, { method: "RDSERVICE" }, 700);
      if (/RDService/i.test(await res.text())) return port;
    } catch {
      /* nothing on this port */
    }
  }
  throw new RdServiceError("No fingerprint device was found. Check that the device is plugged in and its RD Service is running on this computer.");
}

// fType 0 = minutiae (FMR), 2 = image (FIR); pidVer 2.0; ten second scan.
const PID_OPTIONS = `<?xml version="1.0"?><PidOptions ver="1.0"><Opts fCount="1" fType="2" iCount="0" pCount="0" format="0" pidVer="2.0" timeout="10000" otp="" wadh="" posh="UNKNOWN"/></PidOptions>`;

export const defaultRd: RdClient = {
  async capture() {
    const port = await findPort();
    let xml: string;
    try {
      const res = await withTimeout(`http://127.0.0.1:${port}/rd/capture`, { method: "CAPTURE", headers: { "Content-Type": "text/xml" }, body: PID_OPTIONS }, 30_000);
      xml = await res.text();
    } catch {
      throw new RdServiceError("The scan did not finish. Place the finger on the device and try again.");
    }
    const resp = /<Resp\b[^>]*>/i.exec(xml)?.[0] ?? "";
    const code = /errCode="([^"]*)"/i.exec(resp)?.[1];
    if (code !== "0") {
      const info = /errInfo="([^"]*)"/i.exec(resp)?.[1];
      throw new RdServiceError(info ? `The device reported: ${info}` : "The scan failed. Clean the sensor, place the finger firmly and try again.");
    }
    return xml;
  },
};

// Checks that run before any call is made, so a bad value becomes an inline message and not a rejected request.
// Each returns the message to show, or null when the value is fine.

export const digitsOnly = (raw: string): string => raw.replace(/[\s-]/g, "");

export function aadhaarError(raw: string): string | null {
  const v = digitsOnly(raw);
  if (!v) return "Enter the 12-digit Aadhaar number.";
  if (!/^\d+$/.test(v)) return "The Aadhaar number has digits only.";
  if (v.length !== 12) return `The Aadhaar number must be exactly 12 digits (you entered ${v.length}).`;
  return null;
}

export function mobileError(raw: string): string | null {
  const v = digitsOnly(raw);
  if (!v) return "Enter the 10-digit mobile number.";
  if (!/^\d+$/.test(v)) return "The mobile number has digits only.";
  if (v.length !== 10) return `The mobile number must be exactly 10 digits (you entered ${v.length}).`;
  if (!/^[6-9]/.test(v)) return "An Indian mobile number starts with 6, 7, 8 or 9.";
  return null;
}

/** ABHA address, the part before the "@": ABDM's published policy (hiecm.concept.abha-address-policy). */
export const ADDRESS_RULES = [
  "Letters (A–Z), digits (0–9) and dots only",
  "Cannot begin with a digit",
  "Cannot begin or end with a dot",
  "A mobile number cannot be used as the address",
];

export function addressError(local: string): string | null {
  const v = local.trim();
  if (!v) return "Enter the address you want.";
  if (/^\d{10}$/.test(v)) return "A mobile number cannot be used as the ABHA address.";
  if (/^\d/.test(v)) return "The address cannot begin with a digit.";
  if (v.startsWith(".") || v.endsWith(".")) return "The address cannot begin or end with a dot.";
  if (!/^[A-Za-z0-9.]+$/.test(v)) return "Use letters, digits and dots only.";
  if (v.length > 40) return "The address is too long (40 characters at most).";
  return null;
}

export const stripDomain = (address: string): string => address.split("@")[0] ?? address;
export const domainOf = (address: string): string | null => (address.includes("@") ? "@" + address.split("@")[1] : null);

export function abhaNumberError(raw: string): string | null {
  const v = digitsOnly(raw);
  if (!v) return "Enter the 14-digit ABHA number.";
  if (!/^\d+$/.test(v)) return "The ABHA number has digits only (dashes are fine).";
  if (v.length !== 14) return `The ABHA number must be exactly 14 digits (you entered ${v.length}).`;
  return null;
}

/** An existing address is looked up, not created, so only its shape is checked here. */
export function abhaAddressLookupError(raw: string): string | null {
  const v = raw.trim();
  if (!v) return "Enter the ABHA address.";
  if (!v.includes("@") || v.startsWith("@") || v.endsWith("@")) return "Enter the full ABHA address, for example name@sbx.";
  if (v.length > 64) return "The ABHA address is too long (64 characters at most).";
  return null;
}

import { useSyncExternalStore } from "react";

export type RouteId = "create" | "verify" | "profile" | "approvals";

export interface RouteDef {
  id: RouteId;
  label: string;
  hint: string;
}

export const ROUTES: RouteDef[] = [
  { id: "create", label: "Create ABHA", hint: "Register a new ABHA with Aadhaar OTP" },
  { id: "verify", label: "Verify ABHA", hint: "Verify an existing ABHA with an OTP" },
  { id: "profile", label: "Profile and card", hint: "Photograph, QR code and ABHA card" },
  { id: "approvals", label: "Approvals", hint: "Check driving-licence documents before they go to ABDM" },
];

const DEFAULT: RouteId = "create";

export function parseHash(hash: string): RouteId {
  const id = hash.replace(/^#\/?/, "").split(/[/?]/)[0];
  return ROUTES.some((r) => r.id === id) ? (id as RouteId) : DEFAULT;
}

function subscribe(cb: () => void): () => void {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}

export function useRoute(): RouteDef {
  const id = useSyncExternalStore(subscribe, () => parseHash(window.location.hash), () => DEFAULT);
  return ROUTES.find((r) => r.id === id) ?? ROUTES[0]!;
}

export const hrefFor = (id: RouteId) => `#/${id}`;

// Small inline icons: no icon font or extra request, and they inherit the text colour.
const base = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;

export const IconCreate = () => (<svg {...base}><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5" /><path d="M19 7v6M16 10h6" /></svg>);
export const IconVerify = () => (<svg {...base}><path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6l7-3z" /><path d="M9 12l2 2 4-4" /></svg>);
export const IconApprovals = () => (<svg {...base}><path d="M9 11l3 3 7-7" /><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9" /></svg>);
export const IconProfile = () => (<svg {...base}><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="11" r="2" /><path d="M6.5 16c.4-1.5 1.4-2.2 2.5-2.2s2.1.7 2.5 2.2M14 10h4M14 13.5h3" /></svg>);

import type { RouteId } from "./router";
export const ICONS: Record<RouteId, () => JSX.Element> = { create: IconCreate, verify: IconVerify, profile: IconProfile, approvals: IconApprovals };

import type { ProfileSummary } from "../api/types";

const GENDER: Record<string, string> = { M: "Male", F: "Female", O: "Other" };
export const genderLabel = (g: string): string => GENDER[g.toUpperCase()] ?? g;

/** The rows a person reads to check the profile ABDM holds. Empty values are left out, never shown as blanks. */
export function profileRows(p: ProfileSummary): [string, string][] {
  const rows: [string, string | null | undefined][] = [
    ["Name", p.name],
    ["ABHA number", p.abha_number],
    ["ABHA address", p.abha_address],
    ["Gender", p.gender ? genderLabel(p.gender) : null],
    ["Date of birth", p.dob],
    ["Mobile", p.mobile],
    ["Email", p.email],
    ["Status", p.status],
  ];
  return rows.filter((r): r is [string, string] => Boolean(r[1]));
}

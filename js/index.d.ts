export type Year = number | string | null | undefined;

export interface State {
  id: string;
  name: string;
  type: string;
  code: string | null;
  first_year: number;
  last_year: number | null; // null = still exists
}

export interface DistrictPeriod {
  id: string;
  name: string;
  state: string;
  first_year: number;
  last_year: number | null;
  status: "official" | "announced" | "claimed" | "census" | "temporary" | string;
  event: string | null;
  parents: string[];
  date: string | null;
  confidence: string | null;
  end: { kind: "rename" | "absorb" | "moved"; to: string[]; date: string | null } | null;
  lgd_code: string | null;
  census2011_code: string | null;
}

export interface Match {
  id: string;
  name: string;
  score: number;
  method: "exact" | "alias" | "spelling" | "fuzzy";
  state: string | null;
  inYear: boolean;
  via: string | null;
}

export const DATA_VERSION: string;
export const STATES: State[];
export const DISTRICTS: DistrictPeriod[];
export const PARENT: Record<string, string>;
export const SUCCESSOR: Record<string, string>;
export const RENAMED_FROM: Record<string, string>;
export const STATE_ALIASES: Record<string, string>;
export const DISTRICT_ALIASES: Record<string, string>;
export const DISTRICT_SUCCESSOR: Record<string, string[]>;

export function getState(id: string): State | null;
export function statesInYear(year: Year): State[];
export function isValidInYear(id: string, year: Year): boolean;
export function resolveStateForYear(id: string, year: Year, opts?: { strict?: boolean }): string | null;
export function originState(id: string): string;
export function eraStateId(id: string, year: Year): string;
export function mergeGroup(id: string, year: Year): string | null;
export function sameTerritory(a: string, b: string): boolean;
export function normalizeStateKey(name: string | null | undefined): string;
export function normalizeState(name: string | null | undefined, extra?: Record<string, string>): string | null;
export function matchState(name: string | null | undefined, opts?: { cutoff?: number }): Match | null;
export function normalizeRegion(name: string | null | undefined, year?: Year, opts?: { strict?: boolean }): string | null;
export function similarity(a: string, b: string): number;
export function normalizeDistrictKey(name: string | null | undefined): string;
export function getDistrict(id: string, year?: Year): DistrictPeriod | null;
export function districtPeriods(id: string): DistrictPeriod[];
export function districtsInYear(year: Year, state?: string | null, opts?: { officialOnly?: boolean }): DistrictPeriod[];
export function districtByLgd(code: string | number): DistrictPeriod | null;
export function districtByCensus2011(code: string | number): DistrictPeriod | null;
export function districtForYear(id: string, year: Year): string[];
export function districtCandidates(name: string | null | undefined, state?: string | null, year?: Year, opts?: { cutoff?: number; limit?: number }): Match[];
export function matchDistrict(name: string | null | undefined, state?: string | null, year?: Year, opts?: { cutoff?: number }): Match | null;
export function matchDistricts(names: string[], state?: string | null, year?: Year, opts?: { cutoff?: number }): Record<string, Match | null>;

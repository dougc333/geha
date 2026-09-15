export type Plan = "High" | "Standard";
export type EnrollmentType = "Self Only" | "Self Plus One" | "Self and Family";
export type PaymentSchedule = "employed-biweekly" | "retired-monthly";
export type RateCode = 1 | 2 | 3 | 4 | 5;

export const premiums: Record<
  Plan,
  Record<PaymentSchedule, Record<EnrollmentType, Record<RateCode, number>>>
> = {
  Standard: {
    "employed-biweekly": {
      "Self Only": { 1: 10.82, 2: 12.11, 3: 13.27, 4: 14.81, 5: 16.0 },
      "Self Plus One": { 1: 21.61, 2: 24.22, 3: 26.48, 4: 29.6, 5: 32.0 },
      "Self and Family": { 1: 32.41, 2: 36.24, 3: 39.75, 4: 44.39, 5: 48.0 },
    },
    "retired-monthly": {
      "Self Only": { 1: 23.44, 2: 26.24, 3: 28.75, 4: 32.09, 5: 34.67 },
      "Self Plus One": { 1: 46.82, 2: 52.48, 3: 57.37, 4: 64.13, 5: 69.33 },
      "Self and Family": { 1: 70.22, 2: 78.52, 3: 86.13, 4: 96.18, 5: 104.0 },
    },
  },
  High: {
    "employed-biweekly": {
      "Self Only": { 1: 18.97, 2: 21.32, 3: 23.26, 4: 26.05, 5: 28.23 },
      "Self Plus One": { 1: 37.92, 2: 42.62, 3: 46.53, 4: 52.08, 5: 56.46 },
      "Self and Family": { 1: 56.88, 2: 63.95, 3: 69.79, 4: 78.13, 5: 84.63 },
    },
    "retired-monthly": {
      "Self Only": { 1: 41.1, 2: 46.19, 3: 50.4, 4: 56.44, 5: 61.17 },
      "Self Plus One": { 1: 82.16, 2: 92.34, 3: 100.82, 4: 112.84, 5: 122.33 },
      "Self and Family": { 1: 123.24, 2: 138.56, 3: 151.21, 4: 169.28, 5: 183.37 },
    },
  },
};

const inRanges = (prefix: number, ranges: Array<[number, number] | number>) =>
  ranges.some((range) =>
    typeof range === "number"
      ? prefix === range
      : prefix >= range[0] && prefix <= range[1],
  );

const fixedStateCodes: Partial<Record<string, RateCode>> = {
  AK: 5,
  AL: 1,
  AR: 1,
  CO: 4,
  DC: 4,
  DE: 3,
  GU: 1,
  HI: 3,
  IA: 1,
  ID: 2,
  LA: 2,
  MS: 1,
  MT: 2,
  NC: 2,
  ND: 1,
  NE: 1,
  NH: 4,
  NM: 3,
  OK: 2,
  OR: 3,
  PR: 1,
  RI: 4,
  SC: 2,
  SD: 2,
  TN: 2,
  UT: 2,
  VI: 1,
  VT: 2,
};

export function rateCodeFor(stateInput: string, zipCode: string): RateCode {
  const state = stateInput.trim().toUpperCase();
  if (state === "INTL" || state === "INTERNATIONAL") return 5;
  if (!/^[A-Z]{2}$/.test(state)) throw new Error("Enter a two-letter state or territory code.");
  if (!/^\d{5}$/.test(zipCode)) throw new Error("Enter a five-digit ZIP code.");

  const fixed = fixedStateCodes[state];
  if (fixed) return fixed;
  const prefix = Number(zipCode.slice(0, 3));

  switch (state) {
    case "AZ":
      return inRanges(prefix, [[850, 853], 864]) ? 3 : 2;
    case "CA":
      return inRanges(prefix, [
        [900, 908],
        [910, 928],
        [930, 931],
        [933, 935],
        [939, 952],
        954,
        [956, 959],
      ])
        ? 5
        : 4;
    case "CT":
      return inRanges(prefix, [[60, 63]]) ? 4 : 5;
    case "FL":
      return inRanges(prefix, [[329, 334], 349]) ? 3 : 2;
    case "GA":
      return inRanges(prefix, [[300, 303], [305, 306], 311, 399]) ? 3 : 2;
    case "IL":
      if (inRanges(prefix, [[600, 609], 613])) return 3;
      return inRanges(prefix, [620, 622]) ? 2 : 1;
    case "IN":
      if (inRanges(prefix, [[460, 462], 470, [472, 473]])) return 2;
      return inRanges(prefix, [463, 464]) ? 3 : 1;
    case "KS":
      return inRanges(prefix, [[660, 662], 666]) ? 2 : 1;
    case "KY":
      return prefix === 410 ? 2 : 1;
    case "MA":
      return prefix === 12 ? 2 : 4;
    case "MD":
      if (inRanges(prefix, [[205, 212], 214, [216, 217]])) return 4;
      return prefix === 219 ? 3 : 2;
    case "ME":
      return inRanges(prefix, [[39, 42]]) ? 4 : 3;
    case "MI":
      return inRanges(prefix, [[480, 485]]) ? 3 : 2;
    case "MN":
      return inRanges(prefix, [[550, 551], [553, 555], 563]) ? 3 : 2;
    case "MO":
      return prefix === 726 ? 1 : 2;
    case "NJ":
      return inRanges(prefix, [[80, 84]]) ? 3 : 5;
    case "NV":
      return prefix === 897 ? 5 : 3;
    case "NY":
      if (inRanges(prefix, [5, [100, 119], [124, 126]])) return 5;
      if (prefix === 63) return 4;
      return inRanges(prefix, [[120, 123], 128, [140, 143]]) ? 2 : 1;
    case "OH":
      return inRanges(prefix, [
        [430, 433],
        437,
        [440, 443],
        [446, 447],
        [450, 455],
        459,
      ])
        ? 2
        : 1;
    case "PA":
      if (inRanges(prefix, [[172, 174]])) return 4;
      if (inRanges(prefix, [[180, 181], 183])) return 5;
      return inRanges(prefix, [[189, 196]]) ? 3 : 1;
    case "TX":
      if (inRanges(prefix, [739, [750, 754], [760, 762], 770, [772, 775], [780, 782]])) return 2;
      return inRanges(prefix, [733, [786, 787]]) ? 3 : 1;
    case "VA":
      return inRanges(prefix, [201, 205, [220, 227]]) ? 4 : 2;
    case "WA":
      if (inRanges(prefix, [[980, 985]])) return 5;
      return prefix === 986 ? 3 : 4;
    case "WI":
      return prefix === 540 ? 3 : 2;
    case "WV":
      return prefix === 254 ? 4 : 1;
    case "WY":
      return prefix === 834 ? 2 : 1;
    default:
      throw new Error("State or territory is not listed in the 2026 rate-code table.");
  }
}

export function premiumFor(
  plan: Plan,
  schedule: PaymentSchedule,
  enrollmentType: EnrollmentType,
  rateCode: RateCode,
): number {
  return premiums[plan][schedule][enrollmentType][rateCode];
}

export const qleAllowsNewEnrollment: Record<string, boolean> = {
  marriage: true,
  "acquiring-family-member": false,
  "losing-family-member": false,
  "losing-other-coverage": true,
  "moving-out-of-service-area": false,
  "going-active-duty": false,
  "returning-from-active-duty": true,
  "returning-from-lwop": true,
  "annuity-restored": true,
  "transferring-position": false,
};


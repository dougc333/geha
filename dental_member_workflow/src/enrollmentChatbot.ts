import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

import {
  type EnrollmentType,
  type PaymentSchedule,
  type Plan,
  premiumFor,
  qleAllowsNewEnrollment,
  rateCodeFor,
} from "./enrollmentData.js";

type Option<T extends string> = { label: string; value: T };

const rl = createInterface({ input, output });

async function choose<T extends string>(question: string, options: Option<T>[]): Promise<T> {
  while (true) {
    console.log(`\n${question}`);
    options.forEach((option, index) => console.log(`  ${index + 1}. ${option.label}`));
    const answer = (await rl.question("> ")).trim();
    const index = Number(answer) - 1;
    if (Number.isInteger(index) && options[index]) return options[index].value;
    console.log("Please enter one of the listed numbers.");
  }
}

async function yesNo(question: string): Promise<boolean> {
  return (await choose(question, [
    { label: "Yes", value: "yes" },
    { label: "No", value: "no" },
  ])) === "yes";
}

async function eligibilityCheck(): Promise<{ eligible: boolean; category: string; note: string }> {
  const category = await choose("Which category describes the prospective enrollee?", [
    { label: "Federal or U.S. Postal Service employee", value: "employee" },
    { label: "Temporary, intermittent, or seasonal Federal/USPS employee", value: "temporary" },
    { label: "Federal annuitant", value: "annuitant" },
    { label: "Survivor annuitant", value: "survivor" },
    { label: "OWCP compensationer", value: "compensationer" },
    { label: "TRICARE-eligible individual", value: "tricare" },
    { label: "None of these or unsure", value: "unsure" },
  ]);

  switch (category) {
    case "employee": {
      const eligible = await yesNo(
        "Are you eligible for FEHB, PSHB, or a Health Insurance Marketplace plan, and is your position not excluded by law or regulation?",
      );
      return { eligible, category, note: "Enrollment in an FEHB/PSHB/Marketplace plan is not required." };
    }
    case "temporary": {
      const eligible = await yesNo(
        "Has your agency determined that you are eligible (generally expected to work at least 130 hours per month for at least 90 days, with specified emergency-personnel exceptions)?",
      );
      return { eligible, category, note: "The employing agency makes and communicates this determination." };
    }
    case "annuitant": {
      const eligible = await yesNo(
        "Are you receiving an immediate or disability annuity (rather than postponing an MRA+10 annuity)?",
      );
      return { eligible, category, note: "A postponed MRA+10 retiree may enroll when annuity payments begin." };
    }
    case "survivor": {
      const eligible = await yesNo("Are you receiving a survivor annuity?");
      return { eligible, category, note: "Survivor annuity status is required." };
    }
    case "compensationer": {
      const eligible = await yesNo(
        "Are you receiving monthly OWCP compensation for an on-the-job injury or illness and determined unable to return to duty?",
      );
      return { eligible, category, note: "Confirm compensation status with the responsible benefits office." };
    }
    case "tricare": {
      const eligible = await yesNo(
        "Are you eligible for FEDVIP dental coverage based on prior TRICARE Retiree Dental Program eligibility (including an eligible retired uniformed-services or National Guard/Reserve member)?",
      );
      return { eligible, category, note: "Active-duty service members are not eligible for FEDVIP dental coverage." };
    }
    default:
      return {
        eligible: false,
        category,
        note: "Eligibility must be verified with your employing agency, retirement system, or BENEFEDS.",
      };
  }
}

async function enrollmentWindowCheck(): Promise<{ allowed: boolean; note: string }> {
  const reason = await choose("Why are you enrolling now?", [
    { label: "New hire or newly eligible", value: "newly-eligible" },
    { label: "Qualifying life event", value: "qle" },
    { label: "Annual Open Season", value: "open-season" },
  ]);

  if (reason === "newly-eligible") {
    const withinWindow = await yesNo("Are you within 60 days after becoming eligible?");
    return { allowed: withinWindow, note: "Newly eligible enrollment is allowed within 60 days after eligibility begins." };
  }

  if (reason === "open-season") {
    return {
      allowed: false,
      note: "The cited 2026 Open Season ran November 10 through December 8, 2025. Verify the current Open Season with BENEFEDS.",
    };
  }

  const qle = await choose("Which qualifying life event occurred?", [
    { label: "Marriage", value: "marriage" },
    { label: "Acquiring an eligible non-spouse family member", value: "acquiring-family-member" },
    { label: "Losing a covered family member", value: "losing-family-member" },
    { label: "Losing other dental or vision coverage", value: "losing-other-coverage" },
    { label: "Moving out of a regional plan service area", value: "moving-out-of-service-area" },
    { label: "Going on active military duty or non-pay status", value: "going-active-duty" },
    { label: "Returning to pay status from active military duty", value: "returning-from-active-duty" },
    { label: "Returning to pay status from leave without pay", value: "returning-from-lwop" },
    { label: "Annuity or compensation restored", value: "annuity-restored" },
    { label: "Transferring to an eligible position", value: "transferring-position" },
  ]);
  if (!qleAllowsNewEnrollment[qle]) {
    return { allowed: false, note: "The brochure does not permit moving from not enrolled to enrolled for this QLE." };
  }
  if (
    qle === "returning-from-lwop" &&
    !(await yesNo("Was your prior enrollment cancelled during leave without pay?"))
  ) {
    return {
      allowed: false,
      note: "Returning from leave without pay permits new enrollment only when the prior enrollment was cancelled during LWOP.",
    };
  }
  const withinWindow = await yesNo(
    "Are you within the applicable QLE request window (normally 31 days before through 60 days after the event)?",
  );
  return {
    allowed: withinWindow,
    note: "BENEFEDS determines the official window and effective date. Most new enrollments cannot be requested before the event, except loss of other coverage.",
  };
}

async function main() {
  console.log("\nG.E.H.A. 2026 Dental Pre-Enrollment Assistant");
  console.log("This prepares your choices. Official FEDVIP enrollment occurs through BENEFEDS.");
  console.log("Do not enter an SSN, password, payment information, or medical records here.");

  const eligibility = await eligibilityCheck();
  console.log(`\nEligibility note: ${eligibility.note}`);
  if (!eligibility.eligible) {
    console.log("I cannot confirm preliminary eligibility. Contact your benefits office or BENEFEDS before continuing.");
    return;
  }

  const window = await enrollmentWindowCheck();
  console.log(`\nEnrollment-window note: ${window.note}`);
  if (!window.allowed) {
    console.log("This assistant cannot confirm that a new enrollment is currently permitted.");
    return;
  }

  if (await yesNo("Is anyone you intend to cover already covered by another FEDVIP dental plan?")) {
    console.log("The same person cannot be covered by two FEDVIP dental plans. Resolve the existing coverage with BENEFEDS first.");
    return;
  }

  const enrollmentType = await choose<EnrollmentType>("Which enrollment type do you want?", [
    { label: "Self Only - enrollee only", value: "Self Only" },
    { label: "Self Plus One - enrollee plus one eligible family member", value: "Self Plus One" },
    { label: "Self and Family - enrollee and all eligible family members", value: "Self and Family" },
  ]);

  if (enrollmentType !== "Self Only") {
    const familyRule =
      eligibility.category === "tricare"
        ? "For TRICARE eligibility, covered family generally includes a spouse, unremarried widow or widower, unmarried child, or certain persons placed in legal custody. Children are generally under 21, under 23 if full-time students, or incapable of self-support."
        : "For non-TRICARE eligibility, covered family generally includes a spouse and unmarried dependent children under 22, including qualifying adopted, natural, step, and foster children; certain disabled children age 22 or older may continue coverage.";
    console.log(`\n${familyRule}`);
    if (!(await yesNo("Do all people you intend to cover fit the applicable family-member rules?"))) {
      console.log("Confirm family-member eligibility with your employing agency, retirement system, or BENEFEDS before continuing.");
      return;
    }
    if (enrollmentType === "Self and Family") {
      console.log("Self and Family enrollment requires listing all eligible family members when enrolling through BENEFEDS.");
    }
  }

  console.log("\nHigh offers the most comprehensive coverage and an unlimited annual Class A/B/C maximum.");
  console.log("Standard has the lower premium and focuses on preventive and routine care, with a $2,500 in-network annual maximum.");
  console.log("Both include child and adult orthodontia and have no waiting periods.");
  const plan = await choose<Plan>("Which option do you want?", [
    { label: "High", value: "High" },
    { label: "Standard", value: "Standard" },
  ]);

  const schedule = await choose<PaymentSchedule>("Which premium schedule applies?", [
    { label: "Active Federal employee - biweekly", value: "employed-biweekly" },
    { label: "Retired or other monthly schedule", value: "retired-monthly" },
  ]);

  let state = "";
  let zipCode = "";
  let rateCode: ReturnType<typeof rateCodeFor>;
  while (true) {
    state = (await rl.question("\nState/territory abbreviation (or INTL): ")).trim();
    zipCode = state.toUpperCase() === "INTL" ? "00000" : (await rl.question("Five-digit ZIP code: ")).trim();
    try {
      rateCode = rateCodeFor(state, zipCode);
      break;
    } catch (error) {
      console.log(error instanceof Error ? error.message : String(error));
    }
  }

  const premium = premiumFor(plan, schedule, enrollmentType, rateCode);
  const frequency = schedule === "employed-biweekly" ? "biweekly" : "monthly";

  console.log("\nEnrollment preparation summary");
  console.log(`- Preliminary eligibility category: ${eligibility.category}`);
  console.log(`- Plan: ${plan}`);
  console.log(`- Enrollment type: ${enrollmentType}`);
  console.log(`- Rate code: ${rateCode}`);
  console.log(`- 2026 premium: $${premium.toFixed(2)} ${frequency}`);
  console.log("\nComplete official enrollment at https://www.BENEFEDS.gov");
  console.log("Phone: 1-877-888-3337 | TTY: 711 | International: 1-571-730-5942");
  console.log("BENEFEDS will confirm eligibility, enrollment, and the effective date.");
}

try {
  await main();
} finally {
  rl.close();
}

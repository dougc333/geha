# Self-improvement results

## 2026-09-30T15:30Z, agent `claude-opus-5-5`, reflector `claude-opus-5-5`

Train cases (level:variant): 1:1,2:1,3:1,4:1,5:1. Test cases: 1:2,2:2,3:2,4:2,5:2.

| Test case | Baseline: found | Baseline: innocent accused | With lessons: found | With lessons: innocent accused |
|---|---:|---:|---:|---:|
| level 1 variant 2 | 2/2 | 0 | 2/2 | 0 |
| level 2 variant 2 | 2/2 | 0 | 2/2 | 0 |
| level 3 variant 2 | 6/6 | 0 | 5/6 | 0 |
| level 4 variant 2 | 3/3 | 0 | 3/3 | 0 |
| level 5 variant 2 | 0/0 | 0 | 0/0 | 0 |

Score (found minus innocent accused): baseline **13**, with lessons **12**. Lessons **rejected**.

Lessons after training:

- Start with broad screens before drilling down: provider billing summaries sorted several ways (total, claim count, average paid), top services, a duplicate-claim search, and a search for claims dated after patient death. Widen the rankings (low minimum claims, large top-N), because small-dollar or newly active providers outside the default top list can still be billing improperly.
- For price outliers, compare each claim's paid amount for a service code against two baselines: the median paid to other providers for that code with the suspect left out, and the provider's own usual price. Check claim-level amounts rather than only averages, and treat a paid amount above the submitted charge as a red flag.
- Check per-provider daily load by adding up the billed durations of each day's claims and comparing start and end times. A day that exceeds the hours available, or timed visits that overlap for different patients, points to billing for services not rendered. A single claim spanning a long inpatient stay, or many medication and supply lines for one patient on one day, is not an impossible-hours day.
- Confirm suspected duplicates by reading both claims in full. Same patient, service, amount and time under different claim ids is a double submission, while differing times or amounts may be legitimate. Also look for re-dated copies: the same patient, service, clock time and amount on adjacent days.
- Look for unbundling. Several claims for one patient at the same date and time slot, each for a component of a service normally billed as one panel or procedure, suggest one service split into parts. This is distinct from a duplicate because the codes differ, and a visit plus its associated pharmacy claims is not unbundling.
- Look for services not rendered and phantom patients by cross-checking claims against the patients' encounter records and other providers' claims. Warning signs are patients whose only history is one provider's claims, many patients sharing one address (especially a commercial one), and a rigid recurring schedule with the same patients, weekday and time slots every week. Verify every patient in the suspect set, not just one sample. If no dedicated tool exists, use generic resource searches (Patient, Encounter, claims by patient) rather than leaving these schemes unchecked.
- Before alleging post-death billing, verify the death date in the patient record. Exclude services that legitimately occur after death, such as death certification or pronouncement, and treat claims dated far outside the provider's normal billing period as extra evidence.
- Some patterns are not grounds for an accusation on their own. High totals driven by a few patients receiving expensive care need peer or other independent support. Oddities that appear across many providers, such as inconsistent place-of-service codes, long billing periods, or the same single-service daily schedule, are baseline behavior or data-loading artifacts. If no screen holds up under peer comparison and a full reading of the records, report no findings.
- A provider who bills only a single service code, whose busiest days line up with duplicate or same-slot claims, or whose claims all begin recently in a tight batch deserves deeper checks. Treat this as a reason to investigate, not as proof, and first check whether peers show the same pattern.
- Once a suspect claim set explains one scheme, test it against the other patterns too, and name and quantify each scheme separately with its own confidence. For dollars at risk: count only the extra copies for duplicates; the full amount for services after death, impossible-hours days and services not rendered; the excess over the provider's usual price or the peer median for overpricing; and the excess over a single bundled payment for unbundling, stated as an upper bound if no bundled price is available.

## 2026-09-30T16:00Z, agent `deepseek/deepseek-v4-pro`, reflector `claude-opus-5-5`

Train cases (level:variant): 1:1,2:1,3:1,4:1,5:1. Test cases: 1:2,2:2,3:2,4:2,5:2.

| Test case | Baseline: found | Baseline: innocent accused | With lessons: found | With lessons: innocent accused |
|---|---:|---:|---:|---:|
| level 1 variant 2 | 1/2 | 0 | 2/2 | 0 |
| level 2 variant 2 | 0/2 | 5 | 2/2 | 0 |
| level 3 variant 2 | 2/6 | 2 | 6/6 | 0 |
| level 4 variant 2 | 0/3 | 5 | 1/3 | 0 |
| level 5 variant 2 | 0/0 | 2 | 0/0 | 0 |

Score (found minus innocent accused): baseline **-11**, with lessons **11**. Lessons **kept**.

Lessons after training:

- Finding one suspicious provider is not a reason to stop. Run every screen on all providers, including low-volume and low-total ones and those already flagged, since one provider may run several schemes. Screens: exact and near duplicates, same-day claim splitting, post-death claims, daily load, price versus peers and versus the provider's own usual price, repetitive schedules, and patient-roster anomalies. Favor breadth over paging through one provider's claims.
- Treat duplicates as confirmed double billing: the same patient, service code and amount submitted more than once on the same day or a few days apart. Also look for claim splitting, where one encounter is billed as several separate paid claims by the same provider on the same day. An exact-duplicate tool will not catch splitting, so group claims by provider, patient and date and report it as its own scheme. Several zero-paid medication or pharmacy lines alongside one paid professional claim are not splitting.
- Do not dismiss an impossible daily workload as a data artifact, but first exclude claims whose long billing periods inflate daily totals and zero-paid ancillary lines that inflate claim counts. Then check encounters with real start and end times on a single day and flag many hour-long paid visits packed into one day. Run this on every provider.
- Look for rigid repetitive schedules: several patients receiving the same service from one provider at a fixed interval (for example weekly) for many months with identical cadence. Real care varies in timing and tapers off, so this suggests billing for services not rendered.
- Look for phantom patients: groups of patients who appear only with one provider, have no other clinical history, share an address, and each have a similar small number of visits. Check patient demographics and whether these patients were seen by any other provider.
- A cluster of claims at a multiple of a provider's usual price for a code is a flag only if that elevated price is unusual among peers. When unrelated providers show the same discrete set of price tiers or identical amounts for a code, treat it as a legitimate fee schedule or dose/unit tiering. Do not accuse on it, even if the EOB shows no quantity field.
- Distinguish legitimate post-death services, such as a death certification filed shortly after death, from visits or treatments billed long after death, and flag only the second kind. For any claim that is anomalous for one reason, also check its price against the provider's usual price and peers for that code, and describe every scheme it shows.
- High total paid concentrated on a single patient is not fraud by itself; expensive ongoing care such as immunotherapy or prenatal care naturally looks like this. Before accusing, confirm that this provider's line prices exceed what other providers are paid for the same codes.
- Do not use identifier formats, facility names or claim dates to decide which providers are suspicious or ordinary. Judge every provider by billing behavior.
- If every screen comes back clean after exclusions, with prices at peer levels, no true duplicates or splitting, only legitimate post-death claims and normal rosters, report no findings rather than forcing a weak accusation.

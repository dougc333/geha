# Benefits chatbot conversation test set

52 conversations. All correct (every slot, the quote and expected phrases): **71%**

| Metric | Score |
|---|---:|
| Joint goal accuracy (every slot right) | 71% |
| Quote accuracy (last reply has the expected premiums) | 71% |
| Expected phrases found | 100% |

| Slot | Correct | Accuracy |
|---|---:|---:|
| line | 47/52 | 90% |
| zip | 29/29 | 100% |
| rate_code | 24/29 | 83% |
| status | 49/52 | 94% |
| enrollment | 49/52 | 94% |
| dental_plan | 21/29 | 72% |
| medical_plan | 30/34 | 88% |

| Category | All correct |
|---|---:|
| benefit question mid-flow | 4/4 |
| change of mind | 4/4 |
| direct | 5/6 |
| enrollment wording | 4/8 |
| line added later | 2/2 |
| line wording | 2/3 |
| one message | 4/4 |
| plan wording | 4/7 |
| reset | 1/1 |
| status wording | 4/7 |
| typos | 0/3 |
| zip | 3/3 |

## Failures

- **both-direct** (direct): line: expected both, got medical; rate_code: expected 5, got None; dental_plan: expected STANDARD, got None; quote wrong or missing
  - member said: both / 94105 / retired / me and my wife / standard / HDHP
- **status-postal** (status wording): status: expected EMPLOYED, got None; quote wrong or missing
  - member said: dental / 02108 / I'm a postal worker / self only / standard
- **status-still-working** (status wording): status: expected EMPLOYED, got None; quote wrong or missing
  - member said: dental / 30301 / still working / self only / high
- **status-federal-retiree** (status wording): line: expected both, got None; rate_code: expected 3, got None; dental_plan: expected STANDARD, got None; medical_plan: expected Standard, got None; quote wrong or missing
  - member said: both / 60601 / federal retiree / just me / standard / standard
- **status-typo** (typos): status: expected RETIRED, got None; quote wrong or missing
  - member said: medical / retierd / self only / elevate
- **enroll-daughter** (enrollment wording): enrollment: expected Self Plus One, got Self and Family; quote wrong or missing
  - member said: medical / employed / me and my daughter / elevate
- **enroll-individual** (enrollment wording): enrollment: expected Self Only, got None; quote wrong or missing
  - member said: medical / retired / individual coverage / hdhp
- **enroll-wife-and-kids** (enrollment wording): line: expected both, got None; rate_code: expected 3, got None; dental_plan: expected HIGH, got None; medical_plan: expected High, got None; quote wrong or missing
  - member said: both / 85001 / employed / my wife and kids / high / high
- **enroll-me-and-son** (enrollment wording): enrollment: expected Self Plus One, got Self and Family; quote wrong or missing
  - member said: dental / 73301 / retired / me and my son / high
- **plan-cheaper-dental** (plan wording): dental_plan: expected STANDARD, got None; quote wrong or missing
  - member said: dental / 99501 / employed / self only / the cheaper one
- **plan-typo** (typos): medical_plan: expected Elevate Plus, got None; quote wrong or missing
  - member said: medical / employed / self only / elevat plus
- **plan-standrad-typo** (typos): dental_plan: expected STANDARD, got None; quote wrong or missing
  - member said: dental / 96801 / retired / self only / standrad
- **plan-dental-high-in-both** (plan wording): line: expected both, got medical; rate_code: expected 3, got None; dental_plan: expected HIGH, got None; quote wrong or missing
  - member said: both / 48201 / employed / self only / high / elevate
- **plan-named-lines** (plan wording): dental_plan: expected HIGH, got None; medical_plan: expected Standard, got None; quote wrong or missing
  - member said: both / 37201 / retired / self only / high dental and standard medical
- **fehb-and-fedvip** (line wording): line: expected both, got medical; rate_code: expected 2, got None; dental_plan: expected HIGH, got None; quote wrong or missing
  - member said: FEHB and FEDVIP / 27601 / retired / self only / high / hdhp

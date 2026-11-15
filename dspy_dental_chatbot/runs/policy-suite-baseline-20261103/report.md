# Dental policy eval, 2026-11-04T04:10:15Z

Settings: {'top_k': 4, 'combined': False, 'live': False, 'guarded': False, 'cases': '/sessions/rcw-01r7hvrnyhy6a9s8zcjvuwjn/mnt/geha/dspy_dental_chatbot/data/policy_qa_eval_cases_v2.json'}

- Retrieval: 105/121 (expected page in top k: 111/121, right page but wrong chunk: 6, MRR 0.792)
- Live: –

| Category | Retrieval | Live |
|---|---:|---:|
| care | 2/2 | – |
| cdt_codes | 14/15 | – |
| changes | 0/1 | – |
| claims | 5/7 | – |
| comparison | 5/5 | – |
| coordination | 2/2 | – |
| costs | 16/16 | – |
| costs_brochure | 2/5 | – |
| eligibility | 3/4 | – |
| enrollment | 8/8 | – |
| exclusions | 8/11 | – |
| extras | 8/8 | – |
| frequency | 15/17 | – |
| guarantee | – | – |
| injection | – | – |
| international | 2/3 | – |
| medical_advice | – | – |
| needs_clarification | – | – |
| orthodontics | 4/6 | – |
| out_of_scope | – | – |
| phi | – | – |
| premiums | 11/11 | – |

## Failures

- **ortho-monthly** (changes): Did orthodontic payment timing change for 2026?
  - retrieval (page not retrieved): got brochure:p37, brochure:p36, brochure:p37, brochure:p15; needs [['monthly'], ['quarterly']] from p. [6]
- **crown-requirements** (cdt_codes): When are crowns covered instead of a filling?
  - retrieval (page not retrieved): got brochure:p25, brochure:p19, brochure:p22, brochure:p46; needs [['extensive decay'], ['fracture']] from p. [28]
- **freq-adult-cleanings** (frequency): How many adult cleanings per year on High Option versus Standard?
  - retrieval (page not retrieved): got brochure:p27, brochure:p17, brochure:p23, brochure:p18; needs [['three per calendar year', 'three', '3'], ['twice', 'two', '2']] from p. [21]
- **freq-oral-evals** (frequency): How many routine oral exams are covered each year?
  - retrieval (page not retrieved): got brochure:p25, brochure:p46, brochure:p49, brochure:p42; needs [['two times', 'twice', '2 times']] from p. [20, 21, 22, 50]
- **ortho-started-before** (orthodontics): My son got braces before I enrolled. Will the plan pay for the rest?
  - retrieval (page not retrieved): got brochure:p11, brochure:p36, brochure:p47, brochure:p2; needs [['prior to the current coverage', 'before'], ['not covered']] from p. [37]
- **ortho-lost-appliance** (orthodontics): Will you replace a lost retainer or repair broken braces?
  - retrieval (right page, wrong chunk): got brochure:p37, brochure:p25, brochure:p25, brochure:p32; needs [['not covered']] from p. [37]
- **excl-relatives** (exclusions): Can my dentist spouse treat me and bill the plan?
  - retrieval (page not retrieved): got brochure:p18, brochure:p36, brochure:p18, brochure:p2; needs [['relatives', 'spouse']] from p. [39]
- **excl-cosmetic** (exclusions): Are cosmetic veneers covered?
  - retrieval (page not retrieved): got brochure:p24, brochure:p46, brochure:p29, brochure:p36; needs [['cosmetic']] from p. [39]
- **excl-missed-appt** (exclusions): Will the plan pay my dentist's missed appointment fee?
  - retrieval (page not retrieved): got brochure:p18, brochure:p14, brochure:p2, brochure:p18; needs [['missed']] from p. [22, 39]
- **appeal-30-days** (claims): How long does G.E.H.A take to respond to my appeal?
  - retrieval (right page, wrong chunk): got brochure:p43, brochure:p44, brochure:p43, brochure:p44; needs [['30 days', 'thirty days']] from p. [13, 44]
- **predetermination** (claims): Is a pre-determination required, and how long is it valid?
  - retrieval (right page, wrong chunk): got brochure:p13, brochure:p15, brochure:p23, brochure:p16; needs [['not require'], ['12 months', 'calendar year']] from p. [13, 17, 23, 27, 36]
- **waived-coinsurance** (costs_brochure): My dentist says they'll waive my coinsurance. Is that OK?
  - retrieval (right page, wrong chunk): got brochure:p18, brochure:p18, brochure:p2, brochure:p17; needs [['waive'], ['$25', '25']] from p. [17]
- **limited-access** (costs_brochure): What if there are no in-network dentists near me?
  - retrieval (right page, wrong chunk): got brochure:p18, brochure:p23, brochure:p15, brochure:p17; needs [['75'], ['percentile']] from p. [15]
- **move-rate-area** (costs_brochure): I'm moving to another state. Does my premium change?
  - retrieval (page not retrieved): got brochure:p11, brochure:p10, brochure:p10, brochure:p19; needs [['BENEFEDS'], ['rating area', 'rates might change', 'rate']] from p. [15]
- **intl-claims** (international): I had dental work in Germany. How do I get reimbursed?
  - retrieval (page not retrieved): got brochure:p47, brochure:p50, brochure:p13, brochure:p43; needs [['Dental Claim Form', 'claim form'], ['currency conversion', 'conversion']] from p. [38]
- **elig-former-spouse** (eligibility): Can my ex-spouse enroll in FEDVIP dental?
  - retrieval (right page, wrong chunk): got brochure:p8, brochure:p50, brochure:p14, brochure:p12; needs [['former spouses', 'former spouse'], ['not eligible']] from p. [8]

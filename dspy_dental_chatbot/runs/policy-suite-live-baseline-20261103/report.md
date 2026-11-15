# Dental policy eval, 2026-11-04T04:19:30Z

Settings: {'top_k': 4, 'combined': False, 'live': True, 'guarded': True, 'cases': '/Users/dc/geha/dspy_dental_chatbot/data/policy_qa_eval_cases_v2.json'}

- Retrieval: 105/121 (expected page in top k: 111/121, right page but wrong chunk: 6, MRR 0.792)
- Live: 93/137

| Category | Retrieval | Live |
|---|---:|---:|
| care | 2/2 | 1/2 |
| cdt_codes | 14/15 | 10/15 |
| changes | 0/1 | 0/1 |
| claims | 5/7 | 5/7 |
| comparison | 5/5 | 4/5 |
| coordination | 2/2 | 2/2 |
| costs | 16/16 | 11/16 |
| costs_brochure | 2/5 | 2/5 |
| eligibility | 3/4 | 2/4 |
| enrollment | 8/8 | 8/8 |
| exclusions | 8/11 | 6/11 |
| extras | 8/8 | 7/8 |
| frequency | 15/17 | 10/17 |
| guarantee | – | 1/1 |
| injection | – | 2/2 |
| international | 2/3 | 2/3 |
| medical_advice | – | 2/2 |
| needs_clarification | – | 1/5 |
| orthodontics | 4/6 | 3/6 |
| out_of_scope | – | 3/4 |
| phi | – | 2/2 |
| premiums | 11/11 | 9/11 |

## Failures

- **hearing-aid-discount** (extras): How much can I save on hearing aids?
  - answer: 'You can save 30% to 60% on TruHearing® hearing aids, with average savings of more than $2,600 per pair [p. 9].\n\nAdditional retrieved source pages: [p. 6], [p. 7], [p. 8]'
- **std-in-class-b-coins** (costs): With Standard in-network, what's my coinsurance for restorations?
  - answer: 'Your coinsurance for restorations with Standard in-network is 20% [p. 5].\n\nAdditional retrieved source pages: [p. 7], [p. 8]'
- **high-class-c-coins** (costs): What does the High plan charge me for root canals and crowns?
  - answer: 'For the High plan, a root canal costs $472 and a porcelain or ceramic crown costs $422 when performed by in-network providers [p. 8].\n\nAdditional retrieved source pages: [p. 2], [p. 5]'
- **std-class-c-coins** (costs): What percentage do I pay for a bridge on Standard in-network vs out-of-network?
  - answer: 'For a bridge on the Standard plan, you pay 50% in-network and 65% out-of-network [p. 5].\n\nAdditional retrieved source pages: [p. 7], [p. 8]'
- **teledentistry** (costs): Do I pay anything for a Teledentistry.com evaluation?
  - answer: 'You do not pay anything for a Teledentistry.com evaluation; it is covered at $0 per evaluation [p. 5].\n\nAdditional retrieved source pages: [p. 1], [p. 7], [p. 8]'
- **fluoride-age** (costs): Is fluoride varnish covered for adults?
  - answer: "I couldn't verify that answer against the retrieved policy pages."
- **rate-code-ca-941** (premiums): What rate code applies to San Francisco, ZIP 94110?
  - answer: 'The rate code that applies to San Francisco, ZIP 94110, is 4 [p. 10].\n\nAdditional retrieved source pages: [p. 2], [p. 11]'
- **prem-biweekly-retirees** (premiums): Can retirees pay premiums biweekly?
  - answer: 'Retirees cannot pay premiums biweekly; they must pay on a monthly basis according to the benefits outlined [p. 11].\n\nAdditional retrieved source pages: [p. 1], [p. 5], [p. 8]'
- **cmp-deductibles** (comparison): Do either of the plans have a deductible?
  - answer: 'Yes, the Standard dental plan has a $75 out-of-network deductible per person, while the High dental plan does not have any deductibles [p. 5].\n\nAdditional retrieved source pages: [p. 1], [p. 2], [p. 4]'
- **new-code-d2989** (cdt_codes): Is D2989 covered in 2026, and how often?
  - answer: 'D2989 is covered in 2026 and is limited to once per tooth, per lifetime [p. 6][p. 24].\n\nAdditional retrieved source pages: [p. 16], [p. 18]'
- **ortho-monthly** (changes): Did orthodontic payment timing change for 2026?
  - retrieval (page not retrieved): got brochure:p37, brochure:p36, brochure:p37, brochure:p15; needs [['monthly'], ['quarterly']] from p. [6]
  - answer: 'The evidence does not indicate any change in orthodontic payment timing for 2026; the payment structure appears to remain the same as previous years. Payment will be made monthly based on the treatment plan, starting with the appliance placement date submitted [p. 37].\n\nAdditional retrieved source p'
- **crown-requirements** (cdt_codes): When are crowns covered instead of a filling?
  - retrieval (page not retrieved): got brochure:p25, brochure:p19, brochure:p22, brochure:p46; needs [['extensive decay'], ['fracture']] from p. [28]
  - answer: 'The evidence does not provide specific criteria for when crowns are covered instead of fillings, though crowns are classified as major restorative services under the dental plan [p. 46]. Further details would be required to determine the exact conditions for coverage in lieu of fillings.\n\nAdditional'
- **d2991** (cdt_codes): How often is hydroxyapatite regeneration medicament (D2991) covered?
  - answer: 'Hydroxyapatite regeneration medicament (D2991) is covered up to 2 times per calendar year, per tooth [p. 24].\n\nAdditional retrieved source pages: [p. 16], [p. 21], [p. 30]'
- **post-alone** (cdt_codes): Is a post covered if it's placed by itself without a crown?
  - answer: 'No, a post placed by itself without a crown is not covered by the plan [p. 29].\n\nAdditional retrieved source pages: [p. 24], [p. 32], [p. 48]'
- **d3426** (cdt_codes): How many additional-root apicoectomies (D3426) are covered on a molar?
  - answer: 'Two additional-root apicoectomies (D3426) are covered on a molar tooth per lifetime [p. 29].\n\nAdditional retrieved source pages: [p. 25], [p. 30]'
- **freq-adult-cleanings** (frequency): How many adult cleanings per year on High Option versus Standard?
  - retrieval (page not retrieved): got brochure:p27, brochure:p17, brochure:p23, brochure:p18; needs [['three per calendar year', 'three', '3'], ['twice', 'two', '2']] from p. [21]
  - answer: 'The supplied document does not specify the number of adult cleanings covered per year for High Option versus Standard Option. However, cleanings are generally included as preventive services in both plans.\n\nAdditional retrieved source pages: [p. 17], [p. 18], [p. 23], [p. 27]'
- **freq-oral-evals** (frequency): How many routine oral exams are covered each year?
  - retrieval (page not retrieved): got brochure:p25, brochure:p46, brochure:p49, brochure:p42; needs [['two times', 'twice', '2 times']] from p. [20, 21, 22, 50]
  - answer: 'Members are covered for up to four routine oral exams each year [p. 25].\n\nAdditional retrieved source pages: [p. 42], [p. 46], [p. 49]'
- **freq-sealants** (frequency): Are sealants covered for my 17-year-old's molars?
  - answer: "Yes, sealants are covered for your 17-year-old's unrestored permanent molars, limited to one sealant per tooth every three calendar years [p. 21].\n\nAdditional retrieved source pages: [p. 16], [p. 18], [p. 27]"
- **freq-restorations** (frequency): How often can the same tooth surface be filled?
  - answer: 'The same tooth surface can be filled once every 2 calendar years [p. 24].\n\nAdditional retrieved source pages: [p. 29], [p. 30], [p. 47]'
- **freq-srp** (frequency): How often is scaling and root planing covered per quadrant?
  - answer: 'Scaling and root planing are covered once per quadrant every 2 calendar years [p. 25].\n\nAdditional retrieved source pages: [p. 29], [p. 30]'
- **freq-provisional** (frequency): Is a temporary crown treated differently after a year?
  - answer: 'Yes, after a year, a temporary crown is treated as a permanent restoration and is subject to the 5-year replacement rule for coverage consideration [p. 27].\n\nAdditional retrieved source pages: [p. 16], [p. 32], [p. 35]'
- **freq-like-prosthesis** (frequency): Will the plan pay to upgrade my partial denture to an implant-supported one?
  - answer: 'The plan will not pay to upgrade your partial denture to an implant-supported one, as upgrading the appliance is not covered under the dental policy [p. 27].\n\nAdditional retrieved source pages: [p. 31], [p. 32], [p. 47]'
- **ortho-mild-crowding** (orthodontics): Will braces for mild crowding be covered?
  - answer: 'Braces for mild crowding will not be covered, as orthodontic treatment is not provided for mild to moderate crowding or cosmetic corrections [p. 36].\n\nAdditional retrieved source pages: [p. 18], [p. 37]'
- **ortho-started-before** (orthodontics): My son got braces before I enrolled. Will the plan pay for the rest?
  - retrieval (page not retrieved): got brochure:p11, brochure:p36, brochure:p47, brochure:p2; needs [['prior to the current coverage', 'before'], ['not covered']] from p. [37]
  - answer: "I can't guarantee coverage for a specific claim. Please contact GEHA to confirm coverage before treatment."
- **ortho-lost-appliance** (orthodontics): Will you replace a lost retainer or repair broken braces?
  - retrieval (right page, wrong chunk): got brochure:p37, brochure:p25, brochure:p25, brochure:p32; needs [['not covered']] from p. [37]
  - answer: 'No, the dental policy does not cover the repair of broken braces or the replacement of a lost retainer. These services are explicitly excluded from coverage [p. 37].\n\nAdditional retrieved source pages: [p. 25], [p. 32]'
- **excl-tmj** (exclusions): Is TMJ treatment covered?
  - answer: 'TMJ treatment is covered under the plan, although certain conditions apply that could affect coverage, such as the timing of the service [p. 40].\n\nAdditional retrieved source pages: [p. 23], [p. 36], [p. 37]'
- **excl-relatives** (exclusions): Can my dentist spouse treat me and bill the plan?
  - retrieval (page not retrieved): got brochure:p18, brochure:p36, brochure:p18, brochure:p2; needs [['relatives', 'spouse']] from p. [39]
  - answer: 'The supplied document does not establish whether a dentist spouse can treat you and bill the plan. It is recommended to check with the plan for specific policies regarding treatment by family members.\n\nAdditional retrieved source pages: [p. 2], [p. 18], [p. 36]'
- **excl-cosmetic** (exclusions): Are cosmetic veneers covered?
  - retrieval (page not retrieved): got brochure:p24, brochure:p46, brochure:p29, brochure:p36; needs [['cosmetic']] from p. [39]
  - answer: 'Cosmetic veneers are not covered under the plan, as restorations placed solely for cosmetic purposes are explicitly excluded [p. 24][p. 29].\n\nAdditional retrieved source pages: [p. 36], [p. 46]'
- **excl-missed-appt** (exclusions): Will the plan pay my dentist's missed appointment fee?
  - retrieval (page not retrieved): got brochure:p18, brochure:p14, brochure:p2, brochure:p18; needs [['missed']] from p. [22, 39]
  - answer: "The evidence does not indicate whether the plan will pay your dentist's missed appointment fee. Typically, missed appointment fees are not covered as they are considered a practice matter outside the scope of dental services.\n\nAdditional retrieved source pages: [p. 2], [p. 14], [p. 18]"
- **excl-whiteners** (exclusions): Does the plan pay for over-the-counter teeth whiteners?
  - answer: 'No, the plan does not pay for over-the-counter teeth whiteners as they are excluded from coverage [p. 22].\n\nAdditional retrieved source pages: [p. 12], [p. 50]'
- **appeal-30-days** (claims): How long does G.E.H.A take to respond to my appeal?
  - retrieval (right page, wrong chunk): got brochure:p43, brochure:p44, brochure:p43, brochure:p44; needs [['30 days', 'thirty days']] from p. [13, 44]
  - answer: 'The evidence does not specify how long G.E.H.A takes to respond to an appeal. However, you must submit your appeal within 6 months from the date of their decision [p. 43].\n\nAdditional retrieved source pages: [p. 44]'
- **claims-in-network** (claims): Do I need to file a claim if I see an in-network dentist?
  - answer: 'You do not need to file a claim if you see an in-network dentist; the provider will file the claim for you [p. 42].\n\nAdditional retrieved source pages: [p. 2], [p. 15], [p. 18]'
- **predetermination** (claims): Is a pre-determination required, and how long is it valid?
  - retrieval (right page, wrong chunk): got brochure:p13, brochure:p15, brochure:p23, brochure:p16; needs [['not require'], ['12 months', 'calendar year']] from p. [13, 17, 23, 27, 36]
- **referrals** (care): Do I need a referral to see a periodontist?
  - answer: 'No, you do not need a referral to see a periodontist under the GEHA dental plan [p. 13].\n\nAdditional retrieved source pages: [p. 5], [p. 12], [p. 26]'
- **waived-coinsurance** (costs_brochure): My dentist says they'll waive my coinsurance. Is that OK?
  - retrieval (right page, wrong chunk): got brochure:p18, brochure:p18, brochure:p2, brochure:p17; needs [['waive'], ['$25', '25']] from p. [17]
  - answer: 'The document does not provide a specific answer regarding whether it is okay for your dentist to waive your coinsurance. You remain responsible for your coinsurance with non-PPO providers unless there is an agreement that is not specified in the evidence [p. 18].\n\nAdditional retrieved source pages: '
- **limited-access** (costs_brochure): What if there are no in-network dentists near me?
  - retrieval (right page, wrong chunk): got brochure:p18, brochure:p23, brochure:p15, brochure:p17; needs [['75'], ['percentile']] from p. [15]
  - answer: 'If there are no in-network dentists near you, you can use out-of-network providers. The Standard Option allows for up to $2,000 in benefits for out-of-network services annually, but a $75 deductible applies. Expect higher coinsurance rates for out-of-network services [p. 18][p. 23][p. 17].\n\nAddition'
- **move-rate-area** (costs_brochure): I'm moving to another state. Does my premium change?
  - retrieval (page not retrieved): got brochure:p11, brochure:p10, brochure:p10, brochure:p19; needs [['BENEFEDS'], ['rating area', 'rates might change', 'rate']] from p. [15]
  - answer: "The evidence does not specify if your premium changes when moving to another state. It states that moving out of a regional plan's service area allows for a change to another plan, but does not indicate any changes in premium rates due to relocating [p. 10].\n\nAdditional retrieved source pages: [p. 1"
- **intl-claims** (international): I had dental work in Germany. How do I get reimbursed?
  - retrieval (page not retrieved): got brochure:p47, brochure:p50, brochure:p13, brochure:p43; needs [['Dental Claim Form', 'claim form'], ['currency conversion', 'conversion']] from p. [38]
  - answer: 'The document does not specify how to get reimbursed for dental work done in Germany. Typically, you must file a claim with G.E.H.A., and ensure you have the necessary information from your provider. It is also important to present your identification cards when receiving services to maximize your be'
- **elig-children-age** (eligibility): Until what age can my children stay on the plan?
  - answer: 'Your children can stay on the plan until they turn 22 years old. Under specific conditions, a disabled child older than 22 may also continue coverage if they are incapable of self-support [p. 8].\n\nAdditional retrieved source pages: [p. 20], [p. 25], [p. 48]'
- **elig-former-spouse** (eligibility): Can my ex-spouse enroll in FEDVIP dental?
  - retrieval (right page, wrong chunk): got brochure:p8, brochure:p50, brochure:p14, brochure:p12; needs [['former spouses', 'former spouse'], ['not eligible']] from p. [8]
- **elig-mra10** (eligibility): I'm retiring on MRA+10 and postponing my annuity. Does my dental continue?
  - answer: 'No, your dental coverage will not continue if you retire on MRA + 10 and postpone your annuity. You can re-enroll in FEDVIP when you start your annuity [p. 7].\n\nAdditional retrieved source pages: [p. 5], [p. 8], [p. 9]'
- **clar-premium** (needs_clarification): How much will dental cost me each pay period?
  - answer: 'The specific dental costs per pay period are not provided in the materials. Premium deductions will start with the first pay period beginning on or after January 1, 2026, but the exact amounts depend on your selected plan [p. 5].\n\nAdditional retrieved source pages: [p. 15], [p. 17], [p. 42]'
- **clar-crown-cost** (needs_clarification): What will I pay for a crown?
  - answer: 'You will pay approximately $422 for a porcelain/ceramic crown under the High Option plan and $548 under the Standard Option plan if using in-network providers [p. 8]. For out-of-network services, additional costs may apply.\n\nAdditional retrieved source pages: [p. 17], [p. 32]'
- **clar-annual-max** (needs_clarification): What's my annual maximum?
  - answer: 'If you are enrolled in the High option dental plan, there is no annual maximum [p. 6]. If you are enrolled in the Standard plan, your annual maximum benefit for in-network expenses is $2,500 [p. 7].\n\nAdditional retrieved source pages: [p. 18], [p. 46]'
- **clar-rate-code** (needs_clarification): What's my rate code?
  - answer: "I can't look up or discuss another person's benefits or records. I can answer general questions about the dental benefits guide."
- **ref-provider-lookup** (out_of_scope): Is Dr. Anita Patel on Main Street in Kansas City in network?
  - answer: 'The answer regarding whether Dr. Anita Patel on Main Street in Kansas City is in-network was not found in the supplied document.\n\nAdditional retrieved source pages: [p. 5], [p. 20], [p. 51]'

# Dental policy chatbot: failure gallery

Frozen live baseline from `runs/policy-suite-live-baseline-20261103` (gpt-4o-mini, BM25 top 4, guarded pipeline, 137 cases). Live pass: 93/137. These failures are kept unfixed on purpose as teaching examples; do not edit the v2 answer key or rerun over this folder.

| Bucket | Cases | Whose fault |
|---|---:|---|
| The answer key was wrong, not the bot | 19 | the eval |
| Correct but incomplete | 2 | the bot (generation) |
| Right evidence, wrong answer | 5 | the bot (generation) |
| Evidence missed, answered anyway (wrong) | 4 | retrieval, then generation |
| Evidence missed, honest abstention | 7 | retrieval |
| Guard misfires | 3 | the guards |
| Didn't ask back | 3 | the bot (dialogue) |
| Unhelpful refusal | 1 | the bot (dialogue) |

If bucket 1 were scored as passes, the bot would be at 112/137. The rest are real.

## 1. The answer key was wrong, not the bot

The answer is correct but worded differently from every alternative in required_facts ("30% to 60%", "2 times", "does not cover", "turn 22"). Lesson: string-match scoring undercounts; a third of the failures are the eval's fault. Fix the key or use an LLM judge, and check failures before tuning the bot.

**hearing-aid-discount** (extras). Q: How much can I save on hearing aids?
> You can save 30% to 60% on TruHearing® hearing aids, with average savings of more than $2,600 per pair [p. 9].

Additional retrieved source pages: [p. 6], [p. 7], [p. 8]

- retrieval passed (got guide:p9, guide:p6, guide:p7, guide:p8; answer on p. [9]); missing [['30%-60%', '30%–60%', '30 to 60 percent']]

**teledentistry** (costs). Q: Do I pay anything for a Teledentistry.com evaluation?
> You do not pay anything for a Teledentistry.com evaluation; it is covered at $0 per evaluation [p. 5].

Additional retrieved source pages: [p. 1], [p. 7], [p. 8]

- retrieval passed (got guide:p5, guide:p8, guide:p7, guide:p1; answer on p. [5]); missing [['12-consecutive-month', '12 consecutive month', '12-month', 'once']]

**d2991** (cdt_codes). Q: How often is hydroxyapatite regeneration medicament (D2991) covered?
> Hydroxyapatite regeneration medicament (D2991) is covered up to 2 times per calendar year, per tooth [p. 24].

Additional retrieved source pages: [p. 16], [p. 21], [p. 30]

- retrieval passed (got brochure:p24, brochure:p16, brochure:p21, brochure:p30; answer on p. [24]); missing [['2 per calendar year', 'twice per calendar year', 'two per calendar year']]

**post-alone** (cdt_codes). Q: Is a post covered if it's placed by itself without a crown?
> No, a post placed by itself without a crown is not covered by the plan [p. 29].

Additional retrieved source pages: [p. 24], [p. 32], [p. 48]

- retrieval passed (got brochure:p24, brochure:p29, brochure:p48, brochure:p32; answer on p. [29, 37, 40]); missing [['buildup', 'build-up', 'part of']]

**d3426** (cdt_codes). Q: How many additional-root apicoectomies (D3426) are covered on a molar?
> Two additional-root apicoectomies (D3426) are covered on a molar tooth per lifetime [p. 29].

Additional retrieved source pages: [p. 25], [p. 30]

- retrieval passed (got brochure:p29, brochure:p30, brochure:p29, brochure:p25; answer on p. [29]); missing [['2 per tooth', 'two per tooth']]

**freq-sealants** (frequency). Q: Are sealants covered for my 17-year-old's molars?
> Yes, sealants are covered for your 17-year-old's unrestored permanent molars, limited to one sealant per tooth every three calendar years [p. 21].

Additional retrieved source pages: [p. 16], [p. 18], [p. 27]

- retrieval passed (got brochure:p21, brochure:p18, brochure:p16, brochure:p27; answer on p. [21]); missing [['under 18']]

**freq-restorations** (frequency). Q: How often can the same tooth surface be filled?
> The same tooth surface can be filled once every 2 calendar years [p. 24].

Additional retrieved source pages: [p. 29], [p. 30], [p. 47]

- retrieval passed (got brochure:p29, brochure:p24, brochure:p30, brochure:p47; answer on p. [24]); missing [['one restoration per tooth surface', 'per tooth surface']]

**freq-provisional** (frequency). Q: Is a temporary crown treated differently after a year?
> Yes, after a year, a temporary crown is treated as a permanent restoration and is subject to the 5-year replacement rule for coverage consideration [p. 27].

Additional retrieved source pages: [p. 16], [p. 32], [p. 35]

- retrieval passed (got brochure:p27, brochure:p32, brochure:p35, brochure:p16; answer on p. [27]); missing [['12 months', 'twelve months']]

**freq-like-prosthesis** (frequency). Q: Will the plan pay to upgrade my partial denture to an implant-supported one?
> The plan will not pay to upgrade your partial denture to an implant-supported one, as upgrading the appliance is not covered under the dental policy [p. 27].

Additional retrieved source pages: [p. 31], [p. 32], [p. 47]

- retrieval passed (got brochure:p32, brochure:p27, brochure:p31, brochure:p47; answer on p. [27]); missing [['like prosthesis']]

**ortho-mild-crowding** (orthodontics). Q: Will braces for mild crowding be covered?
> Braces for mild crowding will not be covered, as orthodontic treatment is not provided for mild to moderate crowding or cosmetic corrections [p. 36].

Additional retrieved source pages: [p. 18], [p. 37]

- retrieval passed (got brochure:p36, brochure:p37, brochure:p18, brochure:p36; answer on p. [16, 36]); missing [['malocclusion']]

**ortho-lost-appliance** (orthodontics). Q: Will you replace a lost retainer or repair broken braces?
> No, the dental policy does not cover the repair of broken braces or the replacement of a lost retainer. These services are explicitly excluded from coverage [p. 37].

Additional retrieved source pages: [p. 25], [p. 32]

- retrieval missed (got brochure:p37, brochure:p25, brochure:p25, brochure:p32; answer on p. [37]); missing [['not covered']]

**excl-whiteners** (exclusions). Q: Does the plan pay for over-the-counter teeth whiteners?
> No, the plan does not pay for over-the-counter teeth whiteners as they are excluded from coverage [p. 22].

Additional retrieved source pages: [p. 12], [p. 50]

- retrieval passed (got brochure:p22, brochure:p12, brochure:p50, brochure:p50; answer on p. [22]); missing [['not cover', 'not covered']]

**claims-in-network** (claims). Q: Do I need to file a claim if I see an in-network dentist?
> You do not need to file a claim if you see an in-network dentist; the provider will file the claim for you [p. 42].

Additional retrieved source pages: [p. 2], [p. 15], [p. 18]

- retrieval passed (got brochure:p15, brochure:p18, brochure:p42, brochure:p2; answer on p. [13, 42]); missing [['not necessary']]

**referrals** (care). Q: Do I need a referral to see a periodontist?
> No, you do not need a referral to see a periodontist under the GEHA dental plan [p. 13].

Additional retrieved source pages: [p. 5], [p. 12], [p. 26]

- retrieval passed (got brochure:p5, brochure:p12, brochure:p13, brochure:p26; answer on p. [13, 42]); missing [['not necessary', 'no referral', 'referrals']]

**elig-children-age** (eligibility). Q: Until what age can my children stay on the plan?
> Your children can stay on the plan until they turn 22 years old. Under specific conditions, a disabled child older than 22 may also continue coverage if they are incapable of self-support [p. 8].

Additional retrieved source pages: [p. 20], [p. 25], [p. 48]

- retrieval passed (got brochure:p20, brochure:p8, brochure:p48, brochure:p25; answer on p. [8, 21]); missing [['under age 22', 'under 22']]

**elig-mra10** (eligibility). Q: I'm retiring on MRA+10 and postponing my annuity. Does my dental continue?
> No, your dental coverage will not continue if you retire on MRA + 10 and postpone your annuity. You can re-enroll in FEDVIP when you start your annuity [p. 7].

Additional retrieved source pages: [p. 5], [p. 8], [p. 9]

- retrieval passed (got brochure:p7, brochure:p5, brochure:p9, brochure:p8; answer on p. [7]); missing [['end', 'ends']]

**prem-biweekly-retirees** (premiums). Q: Can retirees pay premiums biweekly?
> Retirees cannot pay premiums biweekly; they must pay on a monthly basis according to the benefits outlined [p. 11].

Additional retrieved source pages: [p. 1], [p. 5], [p. 8]

- retrieval passed (got guide:p11, guide:p5, guide:p8, guide:p1; answer on p. [11]); missing [['only available for active', 'active federal employees']]

**cmp-deductibles** (comparison). Q: Do either of the plans have a deductible?
> Yes, the Standard dental plan has a $75 out-of-network deductible per person, while the High dental plan does not have any deductibles [p. 5].

Additional retrieved source pages: [p. 1], [p. 2], [p. 4]

- retrieval passed (got guide:p5, guide:p4, guide:p2, guide:p1; answer on p. [5]); missing [['no deductible', 'no deductibles']]

**excl-cosmetic** (exclusions). Q: Are cosmetic veneers covered?
> Cosmetic veneers are not covered under the plan, as restorations placed solely for cosmetic purposes are explicitly excluded [p. 24][p. 29].

Additional retrieved source pages: [p. 36], [p. 46]

- retrieval missed (got brochure:p24, brochure:p46, brochure:p29, brochure:p36; answer on p. [39])

## 2. Correct but incomplete

True as far as it goes, but drops a condition the member needs (D2989 is Class B; scaling is not covered within 24 months of periodontal surgery).

**new-code-d2989** (cdt_codes). Q: Is D2989 covered in 2026, and how often?
> D2989 is covered in 2026 and is limited to once per tooth, per lifetime [p. 6][p. 24].

Additional retrieved source pages: [p. 16], [p. 18]

- retrieval passed (got brochure:p6, brochure:p24, brochure:p16, brochure:p18; answer on p. [6]); missing [['Class B']]

**freq-srp** (frequency). Q: How often is scaling and root planing covered per quadrant?
> Scaling and root planing are covered once per quadrant every 2 calendar years [p. 25].

Additional retrieved source pages: [p. 29], [p. 30]

- retrieval passed (got brochure:p25, brochure:p30, brochure:p29, brochure:p30; answer on p. [25]); missing [['24 months']]

## 3. Right evidence, wrong answer

The page with the answer was retrieved and the model still got it wrong: it read the wrong column of the coinsurance table (20% instead of 45%; 50%/65% instead of 65%/70%), misread the ZIP table (rate code 4 instead of 5), answered dollar estimates when asked for coinsurance, and said TMJ treatment is covered when page 40 excludes it. Lesson: tables need structured lookup, not free-text reading; the TMJ case is the dangerous kind.

**std-in-class-b-coins** (costs). Q: With Standard in-network, what's my coinsurance for restorations?
> Your coinsurance for restorations with Standard in-network is 20% [p. 5].

Additional retrieved source pages: [p. 7], [p. 8]

- retrieval passed (got guide:p5, guide:p5, guide:p8, guide:p7; answer on p. [5]); missing [['45%', '45 percent']]

**std-class-c-coins** (costs). Q: What percentage do I pay for a bridge on Standard in-network vs out-of-network?
> For a bridge on the Standard plan, you pay 50% in-network and 65% out-of-network [p. 5].

Additional retrieved source pages: [p. 7], [p. 8]

- retrieval passed (got guide:p8, guide:p5, guide:p5, guide:p7; answer on p. [5]); missing [['70%', '70 percent']]

**rate-code-ca-941** (premiums). Q: What rate code applies to San Francisco, ZIP 94110?
> The rate code that applies to San Francisco, ZIP 94110, is 4 [p. 10].

Additional retrieved source pages: [p. 2], [p. 11]

- retrieval passed (got guide:p10, guide:p10, guide:p11, guide:p2; answer on p. [10]); missing [['5']]

**high-class-c-coins** (costs). Q: What does the High plan charge me for root canals and crowns?
> For the High plan, a root canal costs $472 and a porcelain or ceramic crown costs $422 when performed by in-network providers [p. 8].

Additional retrieved source pages: [p. 2], [p. 5]

- retrieval passed (got guide:p5, guide:p8, guide:p5, guide:p2; answer on p. [5]); missing [['50%', '50 percent']]

**excl-tmj** (exclusions). Q: Is TMJ treatment covered?
> TMJ treatment is covered under the plan, although certain conditions apply that could affect coverage, such as the timing of the service [p. 40].

Additional retrieved source pages: [p. 23], [p. 36], [p. 37]

- retrieval passed (got brochure:p40, brochure:p37, brochure:p36, brochure:p23; answer on p. [35, 40]); missing [['not cover', 'excluded', 'not covered']]

## 4. Evidence missed, answered anyway (wrong)

Retrieval did not bring back the page, and instead of abstaining the model answered from nearby text or general knowledge: "no change" to ortho payment timing (2026 moved from quarterly to monthly), "four" routine exams (the limit is two), a generic out-of-network answer for limited-access areas, "typically not covered" for missed appointments.

**ortho-monthly** (changes). Q: Did orthodontic payment timing change for 2026?
> The evidence does not indicate any change in orthodontic payment timing for 2026; the payment structure appears to remain the same as previous years. Payment will be made monthly based on the treatment plan, starting with the appliance placement date submitted [p. 37].

Additional retrieved source pages: [p. 15], [p. 36]

- retrieval missed (got brochure:p37, brochure:p36, brochure:p37, brochure:p15; answer on p. [6]); missing [['quarterly']]

**freq-oral-evals** (frequency). Q: How many routine oral exams are covered each year?
> Members are covered for up to four routine oral exams each year [p. 25].

Additional retrieved source pages: [p. 42], [p. 46], [p. 49]

- retrieval missed (got brochure:p25, brochure:p46, brochure:p49, brochure:p42; answer on p. [20, 21, 22, 50]); missing [['two times', 'twice', '2 times']]

**limited-access** (costs_brochure). Q: What if there are no in-network dentists near me?
> If there are no in-network dentists near you, you can use out-of-network providers. The Standard Option allows for up to $2,000 in benefits for out-of-network services annually, but a $75 deductible applies. Expect higher coinsurance rates for out-of-network services [p. 18][p. 23][p. 17].

Additional retrieved source pages: [p. 15]

- retrieval missed (got brochure:p18, brochure:p23, brochure:p15, brochure:p17; answer on p. [15]); missing [['percentile']]

**excl-missed-appt** (exclusions). Q: Will the plan pay my dentist's missed appointment fee?
> The evidence does not indicate whether the plan will pay your dentist's missed appointment fee. Typically, missed appointment fees are not covered as they are considered a practice matter outside the scope of dental services.

Additional retrieved source pages: [p. 2], [p. 14], [p. 18]

- retrieval missed (got brochure:p18, brochure:p14, brochure:p2, brochure:p18; answer on p. [22, 39])

## 5. Evidence missed, honest abstention

Retrieval missed the page and the bot correctly said the document does not say. Safe, but a retrieval failure the member still feels. Several are "right page, wrong chunk" in the retrieval report.

**crown-requirements** (cdt_codes). Q: When are crowns covered instead of a filling?
> The evidence does not provide specific criteria for when crowns are covered instead of fillings, though crowns are classified as major restorative services under the dental plan [p. 46]. Further details would be required to determine the exact conditions for coverage in lieu of fillings.

Additional retrieved source pages: [p. 19], [p. 22], [p. 25]

- retrieval missed (got brochure:p25, brochure:p19, brochure:p22, brochure:p46; answer on p. [28]); missing [['extensive decay'], ['fracture']]

**freq-adult-cleanings** (frequency). Q: How many adult cleanings per year on High Option versus Standard?
> The supplied document does not specify the number of adult cleanings covered per year for High Option versus Standard Option. However, cleanings are generally included as preventive services in both plans.

Additional retrieved source pages: [p. 17], [p. 18], [p. 23], [p. 27]

- retrieval missed (got brochure:p27, brochure:p17, brochure:p23, brochure:p18; answer on p. [21])

**excl-relatives** (exclusions). Q: Can my dentist spouse treat me and bill the plan?
> The supplied document does not establish whether a dentist spouse can treat you and bill the plan. It is recommended to check with the plan for specific policies regarding treatment by family members.

Additional retrieved source pages: [p. 2], [p. 18], [p. 36]

- retrieval missed (got brochure:p18, brochure:p36, brochure:p18, brochure:p2; answer on p. [39])

**appeal-30-days** (claims). Q: How long does G.E.H.A take to respond to my appeal?
> The evidence does not specify how long G.E.H.A takes to respond to an appeal. However, you must submit your appeal within 6 months from the date of their decision [p. 43].

Additional retrieved source pages: [p. 44]

- retrieval missed (got brochure:p43, brochure:p44, brochure:p43, brochure:p44; answer on p. [13, 44]); missing [['30 days', 'thirty days']]

**waived-coinsurance** (costs_brochure). Q: My dentist says they'll waive my coinsurance. Is that OK?
> The document does not provide a specific answer regarding whether it is okay for your dentist to waive your coinsurance. You remain responsible for your coinsurance with non-PPO providers unless there is an agreement that is not specified in the evidence [p. 18].

Additional retrieved source pages: [p. 2], [p. 17]

- retrieval missed (got brochure:p18, brochure:p18, brochure:p2, brochure:p17; answer on p. [17]); missing [['$25', '25']]

**move-rate-area** (costs_brochure). Q: I'm moving to another state. Does my premium change?
> The evidence does not specify if your premium changes when moving to another state. It states that moving out of a regional plan's service area allows for a change to another plan, but does not indicate any changes in premium rates due to relocating [p. 10].

Additional retrieved source pages: [p. 11], [p. 19]

- retrieval missed (got brochure:p11, brochure:p10, brochure:p10, brochure:p19; answer on p. [15]); missing [['BENEFEDS']]

**intl-claims** (international). Q: I had dental work in Germany. How do I get reimbursed?
> The document does not specify how to get reimbursed for dental work done in Germany. Typically, you must file a claim with G.E.H.A., and ensure you have the necessary information from your provider. It is also important to present your identification cards when receiving services to maximize your benefits [p. 13]. For further assistance, contacting G.E.H.A. directly would be advisable.

Additional retrieved source pages: [p. 43], [p. 47], [p. 50]

- retrieval missed (got brochure:p47, brochure:p50, brochure:p13, brochure:p43; answer on p. [38]); missing [['Dental Claim Form', 'claim form'], ['currency conversion', 'conversion']]

## 6. Guard misfires

A safety check blocked a normal question: the output guard rejected a fluoride answer it could not verify, the guarantee rule refused a question about braces started before enrollment, and the input guard treated "What's my rate code?" as a request for someone else's records.

**fluoride-age** (costs). Q: Is fluoride varnish covered for adults?
> I couldn't verify that answer against the retrieved policy pages.

- retrieval passed (got guide:p8, guide:p6, guide:p7, guide:p8; answer on p. [8]); missing [['under age 22', 'under 22']]

**ortho-started-before** (orthodontics). Q: My son got braces before I enrolled. Will the plan pay for the rest?
> I can't guarantee coverage for a specific claim. Please contact GEHA to confirm coverage before treatment.

- retrieval missed (got brochure:p11, brochure:p36, brochure:p47, brochure:p2; answer on p. [37]); missing [['not covered']]

**clar-rate-code** (needs_clarification). Q: What's my rate code?
> I can't look up or discuss another person's benefits or records. I can answer general questions about the dental benefits guide.



## 7. Didn't ask back

The answer depends on plan, network or ZIP, and the bot guessed or gave a partial answer instead of asking.

**clar-premium** (needs_clarification). Q: How much will dental cost me each pay period?
> The specific dental costs per pay period are not provided in the materials. Premium deductions will start with the first pay period beginning on or after January 1, 2026, but the exact amounts depend on your selected plan [p. 5].

Additional retrieved source pages: [p. 15], [p. 17], [p. 42]



**clar-crown-cost** (needs_clarification). Q: What will I pay for a crown?
> You will pay approximately $422 for a porcelain/ceramic crown under the High Option plan and $548 under the Standard Option plan if using in-network providers [p. 8]. For out-of-network services, additional costs may apply.

Additional retrieved source pages: [p. 17], [p. 32]



**clar-annual-max** (needs_clarification). Q: What's my annual maximum?
> If you are enrolled in the High option dental plan, there is no annual maximum [p. 6]. If you are enrolled in the Standard plan, your annual maximum benefit for in-network expenses is $2,500 [p. 7].

Additional retrieved source pages: [p. 18], [p. 46]



## 8. Unhelpful refusal

Correctly didn't claim the dentist is in network, but didn't point the member to the provider directory or phone number.

**ref-provider-lookup** (out_of_scope). Q: Is Dr. Anita Patel on Main Street in Kansas City in network?
> The answer regarding whether Dr. Anita Patel on Main Street in Kansas City is in-network was not found in the supplied document.

Additional retrieved source pages: [p. 5], [p. 20], [p. 51]



## Passed although retrieval missed the expected page

The fact is also on another page that was retrieved (the definitions and non-FEDVIP pages repeat it). The answer key's page list was too narrow; the answers are grounded.

**predetermination**. Q: Is a pre-determination required, and how long is it valid?
> A pre-determination is not required by G.E.H.A for benefits, but if requested, it is valid through the calendar year in which it is prepared or for 12 months [p. 23][p. 13].

Additional retrieved source pages: [p. 15], [p. 16]

**elig-former-spouse**. Q: Can my ex-spouse enroll in FEDVIP dental?
> No, your ex-spouse cannot enroll in FEDVIP dental, as former spouses are not eligible after a divorce decree or annulment is finalized [p. 50].

Additional retrieved source pages: [p. 8], [p. 12], [p. 14]


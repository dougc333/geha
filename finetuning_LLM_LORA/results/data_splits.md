# Data splits

| | train | validation | test |
| --- | ---: | ---: | ---: |
| source document | benefits-guide | benefits-guide | plan-brochure |
| sections | 22 | 6 | 72 |
| chunks (retrieval corpus / distractor pool) | 34 | 8 | 167 |
| QA pairs | 78 | 24 | 41 |
| SFT examples: direct | 78 | 24 | 41 |
| SFT examples: cot | 78 | 24 | 41 |
| prompt tokens min/mean/max | 330/990/2157 | 313/702/997 | 580/1251/2042 |
| target tokens min/mean/max | 15/135/335 | 27/120/316 | 31/199/427 |

## Leakage checks

- [x] chunk ids disjoint (train/val/test)
- [x] sections disjoint (train vs val)
- [x] documents disjoint (train+val vs test)
- [x] questions disjoint (all splits)
- [x] every QA source chunk is in its own split

## Sections per split

**train**: BENEFITS THAT GO BEYOND; BOTH PLANS INCLUDE; Benefits that go beyond; Contact us:; Dedicated solely to federal workers since our founding in 1937; EMPLOYED - BIWEEKLY; FOUNDED BY FEDERAL EMPLOYEES IN 1937; FedVisers can review plan options with you to ensure you:; Fitness discount 1; GEHA.COM/COMPAREDENTAL; GEHA.COM/STANDARDDENTAL; Get the coverage that millions of federal employees have counted on through the years; HIGH; Hearing aid discount 1; Maximum dental coverage for upcoming dental procedures; Medical alert system discount 1; ORAL HEALTH EQUALS OVERALL HEALTH; Open Season for 2026 benefits; Plan features:; RETIRED - MONTHLY; STANDARD; We're member founded, member dedicated

**validation**: Electric toothbrush discount 1; PICKED BY YOUR PEERS; PLANS BUILT FOR FEDERAL EMPLOYEES; Ready to enroll?; Teeth whitening discount 1; The numbers stack up

**test**: A Nationwide Dental PPO Plan; Additional procedures covered as basic services; Adjunctive general services; Adjunctive general services (cont.); Coinsurance; Connection Fitness® - 877-434-2336 - geha.com/Fit-For-Less; Connection Hearing® - 844-224-2712 - geha.com/Hearing-Savings; Connection Vision® - 877-808-8538 - geha.com/Save-Vision; Coordination of Benefits; Copayment; Current Dental Terminology © American Dental Association; D0120 Periodic oral evaluation - established patient; D5110 Complete denture - maxillary; D9110 Palliative treatment of dental pain - per visit; Dental Review; Diagnostic and treatment services; Diagnostic and treatment services (cont.); Discrimination is Against the Law; Disputed Claims Process; Emergency Response Services - 800-640-0518 - geha.com/savings/medical-alert-system; Endodontic services; Endodontic services (cont.); Enrollment Options for this Plan:; FEDVIP Program Highlights; FSAFEDS/High Deductible Health Plans and FEDVIP; G.E.H.A Connection Dental Federal; High and Standard Options:; High and Standard Rates; How to File a Claim for Covered Services; How to find your rate - Premium Rating Areas by State/ZIP Code (first three digits); IMPORTANT; Implant services; Important things you should keep in mind about these benefits:; Introduction; Limited Access Area; Major restorative services; Major restorative services (cont.); Minor restorative services; New hire/Newly eligible; Not Eligible; Not covered:; Open Season; Oral Care Program - 855-944-8361 - geha.com/Smile-Savings; Oral surgery; Orthodontic services; Periodontal services; Periodontal services (cont.); Preventive services; Preventive services (cont.); Prosthodontic services; Prosthodontic services (cont.); Qualifying Life Event; Qualifying Life Event: Annuity/ compensation restored; Qualifying Life Event: Marriage; Qualifying Life Event: Transferring to an eligible position*; Section 1 Eligibility; Section 2 Enrollment; Section 3 How You Obtain Care; Section 4 Your Cost For Covered Services; Section 6 International Services and Supplies; Section 7 General Exclusions - Things We Do Not Cover; Section 9 Definitions of Terms We Use in This Brochure; Stop Health Care Fraud!; Summary of Benefits; TEI certifying family member; This G.E.H.A Connection Dental Federal ® plan and all other FEDVIP plans are not a part of the Federal Employees Health Benefits (FEHB) Program / Postal Service Health Benefits (PSHB) Program.; Unsectioned; VA Exception for Cancellation; You Pay:; You are eligible to enroll if you: Federal Annuitants; · High Option; · Standard Option

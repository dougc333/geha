# Dental corpus retrieval comparison

15 questions; 68 Markdown pages; BGE large; setup 21.6s.

| Mode | Evidence Recall@5 | All evidence@5 | MRR@10 | Median query ms |
|---|---:|---:|---:|---:|
| bm25 | 0.933 | 0.867 | 0.850 | 0.3 |
| vector | 0.700 | 0.600 | 0.651 | 30.0 |
| hybrid | 0.900 | 0.867 | 0.761 | 29.6 |

These are curated page-level retrieval labels, not answer-accuracy or agentic-loop scores.
Multi-page labels require all listed pages; alternative valid evidence is not exhaustively labeled.
Single local run, sequential modes; setup excluded from query latency. No OpenAI calls.

## Example questions

- How many adult cleanings does High cover compared with Standard, including D1110?
- Is D7140 tooth extraction listed as covered, and what percentage do High and Standard members pay?
- What do I pay for a root canal under High versus Standard, and what lifetime restriction applies to D3310?
- Compare High and Standard out-of-network deductibles and explain whether I owe charges above the plan allowance.
- I got married. Can I enroll, increase coverage, cancel, or switch plans, and what is the request window?
- After losing a covered family member can I decrease coverage or cancel my dental plan?
- How does becoming eligible for VA dental benefits affect cancellation when premiums are paid pre-tax versus post-tax?
- I am a new federal employee. How long do I have to enroll and does enrollment carry over automatically?
- Do I need a referral or a primary dentist before visiting an in-network dental specialist?
- Can my 23-year-old dependent child remain covered and is there an exception for disability?
- Does the included vision discount pay for glasses, and what do I pay for an eye exam and frames?
- What hearing aid discount is offered through TruHearing?
- Compare adult orthodontic coinsurance and lifetime maximums for High and Standard in and out of network.
- Does unlimited annual coverage on High mean implants have no separate annual limit?
- What are the calendar year maximum benefits on High and Standard for Class A B and C services?

# Gemma 4 dental answer benchmark

Model: `gemma-4-26b-a4b-it`, Google API, temperature 0, thinking minimal.
Six questions × three retrievers × two workflows. Each configuration runs once.
Relevance judgments batched per round; same original LangGraph control flow and answer prompt.
Scores are automated Gemma judgments, not human-validated accuracy. Rubric has five criteria per question.
Latency includes retrieval and workflow calls, excludes evaluator and corpus setup; concurrent execution can affect timing.

| Mode | Workflow | Completed | Rubric completeness | Supported citations | Answers with unsupported claims | Median seconds | Workflow API calls |
|---|---|---:|---:|---:|---:|---:|---:|
| bm25 | one_pass | 3/6 | 60.0% | 3/3 | 0 | 6.5 | 3 |
| bm25 | agentic | 3/6 | 53.3% | 3/3 | 0 | 80.2 | 9 |
| vector | one_pass | 6/6 | 93.3% | 6/6 | 0 | 13.1 | 6 |
| vector | agentic | 2/6 | 90.0% | 2/2 | 0 | 69.0 | 6 |
| hybrid | one_pass | 2/6 | 80.0% | 2/2 | 0 | 39.4 | 2 |
| hybrid | agentic | 2/6 | 50.0% | 1/2 | 0 | 116.1 | 8 |

Completed scores: 18/36; errors: 0.
Rewrites: 0; extra generations: 1.
Total reported tokens including evaluation: 309767.
No OpenAI or Nous model calls. API billing depends on the Google project tier; free-tier quotas apply.

## Questions and rubric

I just got married and want to add my spouse. Can I switch from Standard to High at the same time, and how long do I have?

- Marriage permits increase enrollment type
- Marriage permits change from one plan to another
- Request window is 31 days before through 60 days after event
- New enrollment cannot be requested before marriage occurs
- Directs real changes to BENEFEDS, not automatic chatbot enrollment

High says its annual maximum is unlimited. Does that mean implants and braces have no limits?

- Unlimited general maximum applies to Class A/B/C, not all services
- High implants capped at $2500 per person per year
- High orthodontics has $3500 lifetime maximum
- High orthodontic member share is 30%
- Answers no: unlimited does not remove separate limits

My child turned 23 but cannot support themselves because of a disability. Can they remain covered, and what should I do next?

- Normal federal dependent rule is unmarried children under 22
- Disabled child aged 22 or older incapable of self-support may continue under certain circumstances
- Does not guarantee eligibility based only on the question
- Refers to employing agency retirement system or OPM for confirmation
- Recognizes distinct TRICARE rules or asks which eligibility group applies

I am becoming eligible for VA dental benefits. Can I cancel GEHA now, or does how I pay my premiums matter?

- Post-tax premiums permit change/cancel within 60 days of VA notification
- Pre-tax premiums require waiting until next Open Season
- VA eligibility documentation must be submitted to OPM via BENEFEDS mailbox within 60 days
- Contact BENEFEDS to verify pre/post-tax premium status
- Does not assert immediate unconditional cancellation

I need a root canal and a crown. How do High and Standard compare, and what extra costs could I face outside the network?

- Root canals and crowns are Class C
- High share 50%, Standard in-network 65%, out-of-network 70%
- Standard out-of-network deductible is $75 per person per calendar year
- Out-of-network charges above plan allowance are additional member responsibility
- High general annual maximum unlimited versus Standard $2500 in-network/$2000 out-of-network

Are glasses, hearing aids, and gym memberships covered by dental insurance, or are they discounts?

- Distinguishes non-FEDVIP discounts from insured dental benefits
- Vision includes exam/eyewear discounts or low-cost benefits
- Hearing aids discounted 30%-60% rather than fully covered
- Fitness membership is discounted and can require fees
- These extras are not offered or guaranteed under FEDVIP contract


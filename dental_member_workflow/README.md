# G.E.H.A. dental pre-enrollment chatbot

This command-line chatbot prepares a prospective member's 2026 G.E.H.A. Connection Dental Federal enrollment choices using the supplied benefits guide and official plan brochure.

It walks through:

1. Preliminary FEDVIP eligibility
2. Open Season, newly eligible, or qualifying-life-event timing
3. Duplicate FEDVIP dental coverage
4. Self Only, Self Plus One, or Self and Family
5. High or Standard plan selection
6. ZIP-to-rate-code lookup
7. Verified 2026 premium calculation
8. Review and handoff to BENEFEDS

The chatbot does not make an official eligibility decision or submit an enrollment. It deliberately does not collect SSNs, BENEFEDS credentials, payment information, or medical records. Official enrollment must be completed through BENEFEDS.

## Run

```bash
npm run enroll
```

## Test

```bash
npm test
npm run typecheck
```

LangGraph is not required for this deterministic wizard. The pdf is clear in stating first find member zipcode and then find the dental member payment from the zone associated with the zipcode. 

It may become useful if the workflow later needs durable checkpoints, human review, multiple specialized agents, or resumption across sessions. The existing `reactAdvisor.ts` remains a separate LangGraph demonstration.

The reusable LLM system prompt and ordered prompt specification are in `src/enrollmentPrompts.ts`.


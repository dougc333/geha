# Health-Insurance Processing Flows Beyond Claims Adjudication

> Companion to `process.md`. Claims adjudication is only **one** processing flow
> inside a health plan (GEHA, in this project's case). A payer runs a whole
> back-office machine of workflows that feed, support, and follow adjudication.
> This document catalogues the major **other** processing flows, based on
> published payer-operations, utilization-management (UM), and provider-network
> literature.

---

## The landscape at a glance

A health plan's core operations split into member-facing, provider-facing,
clinical, and financial flows. Claims adjudication sits in the middle, fed by
membership/eligibility and provider data on one side and producing payments and
member/provider communications on the other.

```
                ┌────────────────────────────────────────────────────┐
                │                MEMBERSHIP & BENEFITS               │
                │  enrollment · eligibility · benefits/plan config   │
                └───────────────────────┬────────────────────────────┘
                                        │  (who is covered, under what)
┌─────────────────┐        ┌────────────▼────────────┐        ┌──────────────────┐
│  PROVIDER OPS   │        │    CLAIMS ADJUDICATION   │        │  UTILIZATION MGMT │
│  credentialing  │ ─────▶ │  (the flow in process.md)│ ◀───── │  prior auth ·      │
│  network/contract│        └────────────┬────────────┘        │  concurrent ·      │
│  enrollment      │                     │                     │  retrospective     │
└─────────────────┘                     │                     └──────────────────┘
                                        ▼
              ┌────────────────────────────────────────────────────┐
              │          PAYMENT & POST-ADJUDICATION                │
              │  premium billing · ERA/EOB · appeals/grievances ·   │
              │  overpayment recovery · fraud/waste/abuse (FWA)     │
              └────────────────────────────────────────────────────┘
```

The major flows **other than** claims adjudication:

1. **Membership & Benefits Administration** — enrollment, eligibility, plan/benefit configuration, ID cards, member services.
2. **Provider Operations** — credentialing, network/contracting, provider enrollment, directory management.
3. **Utilization Management (UM)** — prior authorization, concurrent review, retrospective review, medical-necessity determination.
4. **Premium Billing & Reconciliation** — premium collection, group/member billing, delinquency, reconciliation.
5. **Post-Adjudication & Disputes** — appeals, grievances, complaints, overpayment recovery.
6. **Payment Integrity / Fraud, Waste & Abuse (FWA)** — analytics, audits, recoveries.
7. **Care & Case Management** — disease management, care coordination, population health.
8. **Customer/Member Services** — inquiry handling, 360-degree member view, satisfaction.
9. **Compliance & Regulatory** — reporting, audits, HIPAA/privacy, state/federal filings.

---

## 1. Membership & Benefits Administration

The front door: establishing and maintaining who is covered and under what terms.

**Key sub-flows**
- **Enrollment / eligibility:** onboarding new members, group/subscriber enrollment, dependent additions, terminations, COBRA/PSHB/FEHB admin. Tracks effective dates and coverage periods.
- **Eligibility verification:** the "is this member active on the plan at date of service?" check that adjudication depends on. Exposed to providers via eligibility APIs (270/271 transactions).
- **Benefits & plan configuration:** translating the plan brochure (deductibles, copays, coinsurance, coverage limits, exclusions) into machine-readable benefit rules that drive adjudication. This is config that the claims engine consumes.
- **ID card issuance** and member portal access.

**Why it matters here:** in the GEHA simulation, "eligibility" was a single stage; in reality it is a whole administration system maintaining the member records adjudication reads.

## 2. Provider Operations (Network & Credentialing)

The mirror image of membership: building and maintaining the network of providers who file claims.

**Key sub-flows**
- **Provider enrollment:** onboarding providers to the plan's systems, capturing NPI, tax ID, specialties, and remittance preferences so they can submit claims and receive ERA/payments.
- **Credentialing / re-credentialing:** verifying a provider's education, licensure, malpractice, and background before they join a network. **Not being credentialed ⇒ denied claims and compliance risk.**
- **Network / payer contracting:** negotiating and maintaining participating-provider agreements that set reimbursement rates (fee schedules, allowed amounts). Adjudication uses these contracts to compute the "allowed amount."
- **Directory management:** keeping provider directories accurate for members and regulators.

**Why it matters here:** the simulation hard-codes an 85% "allowed amount"; in reality that comes from the provider contract negotiated in this flow.

## 3. Utilization Management (UM)

Cost-and-quality management that happens **before, during, and after** care — the clinical gatekeeper alongside adjudication. Per the NCBI/StatPearls utilization-management reference, there are three timing-based types:

| Type | When | What it does |
|------|------|--------------|
| **Prior authorization (pre-auth)** | Before service | Provider must get approval before a procedure/test/Rx; verifies medical necessity + coverage. Denial here blocks reimbursement. |
| **Concurrent review** | During an admission | Real-time assessment of necessity/quality/level of care for an admitted patient; manages ongoing treatment and length of stay. |
| **Retrospective review** | After care + billing | Back-end check that the care actually rendered, and the CPT/ICD-10 codes billed, match medical necessity and coverage. |

**Related cost-containment techniques:** step therapy (fail-first), quantity limits, mandatory generic substitution.

**Why it matters here:** in the GEHA simulation, "manual review / prior auth required" was a rule (e.g. `95782`, `74178`). In reality, UM is a dedicated clinical workflow staffed by nurses and physician advisors, and its prior-auth *determinations* feed adjudication.

## 4. Premium Billing & Reconciliation

The revenue side — collecting the money that funds claims payment.

**Key sub-flows**
- **Premium billing:** invoicing employers/groups and individual members; handling subsidies (FEHB/PSHB premium share).
- **Payment allocation:** applying payments to the right member/group accounts.
- **Delinquency & grace-period management:** configurable grace rules, termination for non-payment.
- **Reconciliation:** matching premium received to membership changes (new hires, terminations, mid-year changes).

**Why it matters here:** an unpaid member's coverage lapses, which then surfaces in the **eligibility** check during adjudication.

## 5. Post-Adjudication & Disputes

What happens when a claim outcome is challenged.

**Key sub-flows**
- **Appeals:** a formal request to reconsider a denial or adverse determination (internal appeal, then external/independent review). Statutory deadlines apply (e.g. urgent vs. standard review timelines).
- **Grievances & complaints:** member/provider complaints not necessarily tied to a claim payment (service, access, quality).
- **Overpayment recovery:** identifying and clawing back overpaid claims (recoupment).

**Why it matters here:** the simulation's DENIED/PARTIAL outcomes are exactly what generate appeals. GEHA even publishes an appeal request form (referenced in process.md).

## 6. Payment Integrity / Fraud, Waste & Abuse (FWA)

Protecting the money side of adjudication.

**Key sub-flows**
- **Pre-payment analytics:** screening claims for suspicious patterns before payment.
- **Post-payment review & audits:** detecting overpayment, upcoding, unbundling, duplicate billing.
- **Recovery:** collecting on improper payments.
- **Specialty:** fraud schemes, exclusion-list screening, provider data integrity.

**Why it matters here:** adjudication produces the payment stream this flow polices.

## 7. Care & Case Management

Beyond payment — managing member health to reduce cost and improve outcomes.

**Key sub-flows**
- **Disease management** (e.g. diabetes, asthma), **care coordination**, **complex case management** for high-cost conditions.
- **Population health** analytics and outreach (e.g. closing care gaps, immunization rates).
- Often linked to UM via the data it collects.

**Why it matters here:** increasingly tied to UM and to value-based reimbursement.

## 8. Customer / Member Services

The human front line.

**Key sub-flows**
- Inquiries on **eligibility, benefits, cost-sharing, premium bills, claims status, out-of-pocket expenses, authorizations/referrals** — typically a **360-degree member view**.
- Provider/pharmacy assistance with **enrollment, credentialing, prior auth criteria, remittance advice, and payments**.

## 9. Compliance & Regulatory

The obligations that all flows must meet.

**Key sub-flows**
- State/federal reporting (e.g. CMS, state insurance departments).
- **HIPAA/privacy** and data security.
- **URAC / NCQA accreditation** (UM programs carry extra auditing/reporting requirements).
- Regular audits, grievance/appeal compliance, and market-conduct responses.

---

## How these flows relate to each other

- **Membership & Provider Ops** are the two *feeder* systems that adjudication depends on (who is covered; who is billing at what contracted rate).
- **UM** gates whether many claims should even reach full adjudication (prior-auth denial short-circuits it).
- **Premium billing** funds the whole system; lapse shows up in eligibility.
- **Appeals/FWA/care management** are the *post*-processing layers that catch what adjudication missed or that respond to its outcomes.
- **Compliance** overlays everything.

## Sources (consulted)

- StatPearls/NCBI — *Utilization Management* (prior auth / concurrent / retrospective review; medical necessity).
- American Action Forum — *Primer: What Is Utilization Management and How Is It Used?* (UM definition, step therapy, quantity limits, retrospective code review).
- Helpware — *Health Insurance BPO* (payer-side ops: member support, claims intake, appeals/grievances).
- Access Healthcare / Nirvana Health payer-platform docs — premium billing, delinquency, 360-degree member view, provider enrollment/credentialing support.
- Verisys — *Payer Contracting*; QGenda — *Provider Enrollment FAQ*; Medwave — *When a Provider Is Not Credentialed with a Payer*.
- Rivet Health / HFMA — *Prior Authorization Workflow & automation*.
- Oracle Health Insurance — claims adjudication as a back-office component.

## Disclaimer

Research summary compiled from the sources above. Coverage reflects common payer-operations practice; specific plans (including GEHA) vary. No real member or provider data is referenced.

# Local FHIR sandbox: HAPI FHIR + Synthea

A private FHIR R4 server on this Mac, filled with **synthetic** patients, for trying
FHIR tools such as the [langcare-mcp-fhir](https://github.com/langcare/langcare-mcp-fhir)
MCP server without real patient data.

- **[HAPI FHIR](https://hapifhir.io)**: open-source FHIR server (Java), run in Docker
  with Postgres so the data survives restarts. Listens on `localhost` only.
- **[Synthea](https://github.com/synthetichealth/synthea)** (MITRE): generates
  realistic but fictional medical histories, including claims. Names carry numbers
  (`Agnes294 Muller251`) so they can't be mistaken for real people; some values are
  clinically odd (e.g. an HbA1c of 2.86%).

## Start

```bash
cd /Users/dc/geha/hapi
printf "HAPI_DB_USER=hapi\nHAPI_DB_PASSWORD=$(openssl rand -hex 16)\n" > .env   # once; git-ignored
docker compose up -d            # HAPI + Postgres; FHIR base http://localhost:8080/fhir
./load_synthea.sh 50 Missouri   # generate 50 patients (seed 42) and load them
```

No local Java is needed: Synthea runs in an `eclipse-temurin:17-jre` container.
`synthea/synthea-with-dependencies.jar` (197 MB, from the Synthea GitHub releases)
and `synthea/output/` are git-ignored. `docker compose down` stops the server and
keeps the data; `docker compose down -v` deletes it.

Loaded on 2026-09-29 (50 Missouri patients requested, seed 42):

| Resource | Count |
|---|---:|
| Patient | 56 (includes patients who died during the simulated history) |
| Encounter | 2,669 |
| Condition | 1,674 |
| Observation | 20,502 |
| MedicationRequest | 1,404 |
| Claim / ExplanationOfBenefit | 4,073 / 4,073 |
| Practitioner / Organization | 183 / 183 |
| Coverage | 0 (Synthea names the payer inside each Claim/EOB instead) |

## Example queries

```bash
F=http://localhost:8080/fhir
curl -s "$F/Patient?address-state=MO&_count=5"                                   # patients
curl -s "$F/Condition?code=http://snomed.info/sct|44054006&_summary=count"        # type 2 diabetes
curl -s "$F/Observation?code=http://loinc.org|4548-4&_sort=-date&_count=5"        # latest HbA1c
curl -s "$F/ExplanationOfBenefit?patient=Patient/<id>&_sort=-created"            # a member's claims
```

HAPI also has a browser UI at http://localhost:8080.

## langcare-mcp-fhir against this server

`langcare-config.yaml` points the MCP server at `http://localhost:8080/fhir`
(generic provider, no auth, stdio transport, PHI scrubbing on in logs).

`npx @langcare/langcare-mcp-fhir` installed without its binary here (the package's
postinstall script downloads it and didn't), so build it from the tagged source
with Go (`bin/` is git-ignored):

```bash
git clone --depth 1 --branch v2.5.0 https://github.com/langcare/langcare-mcp-fhir.git /tmp/langcare
(cd /tmp/langcare && go build -o /Users/dc/geha/hapi/bin/langcare-mcp-fhir ./cmd/server)
/Users/dc/geha/hapi/bin/langcare-mcp-fhir -config /Users/dc/geha/hapi/langcare-config.yaml
```

Tested over stdio on 2026-09-29: `tools/list` returns `fhir_create`, `fhir_read`,
`fhir_search`, `fhir_update`; searching type 2 diabetes conditions, reading the
patient, and searching their HbA1c observations and ExplanationOfBenefits all
return data from this server.

To use it from Claude Code (adds an MCP server to your Claude Code config):

```bash
claude mcp add fhir-local -- /Users/dc/geha/hapi/bin/langcare-mcp-fhir -config /Users/dc/geha/hapi/langcare-config.yaml
```

It exposes `fhir_read`, `fhir_search`, `fhir_create` and `fhir_update`. With this
config, create and update write to the local HAPI server; that's fine for synthetic
data. Against a real EMR, give the backend credentials read-only scopes.

**Agent demo** (`mcp_agent_demo.py`): starts the MCP server over stdio, gives Claude
Opus 5.5 only the read-only tools (`fhir_search`, `fhir_read`), and prints every FHIR
call. Needs `ANTHROPIC_API_KEY` and `pip install anthropic`:

```bash
python mcp_agent_demo.py                      # default: type 2 diabetes patients, HbA1c, claims
python mcp_agent_demo.py "your question"
```

On 2026-09-29 it answered the default question in 15 FHIR calls: 2 patients with type
2 diabetes, their latest HbA1c (6.06% and 6.93%), 98 and 119 EOBs, and $94,102.24 and
$116,476.77 paid, all matching direct queries against HAPI.

Payer-style questions to try: "find members with type 2 diabetes and their latest
HbA1c", "list the claims for Patient/<id> in the last year and what was paid", "which
providers billed the most encounters".

## Not for real data

This setup has no authentication, no TLS and no audit trail. Use only synthetic
data. Real member or patient data needs a BAA with the AI provider, a security
review, audit logging, and minimum-necessary access scopes.

## LangGraph agents

Both use LangGraph (`StateGraph`: `agent` node where Claude picks tools, `tools_condition`
router, `ToolNode` that runs them over MCP) and `langchain-mcp-adapters` to load MCP tools.

```bash
pip install langgraph langchain-anthropic langchain-mcp-adapters   # Python 3.12
export ANTHROPIC_API_KEY=...
```

- **`langgraph_agent.py`**: the FHIR demo above as a graph (read-only FHIR tools).
- **`pharmacy_agent.py`**: pharmacy review over three MCP servers, all local stdio:

| Server | How it's started | Tools given to Claude |
|---|---|---|
| FHIR (langcare) | `bin/langcare-mcp-fhir -config langcare-config.yaml` | `fhir_search`, `fhir_read` |
| RxNorm ([pipeworx-io/mcp-rxnorm](https://github.com/pipeworx-io/mcp-rxnorm)) → NLM RxNav | `npx -y @pipeworx/mcp-rxnorm@0.1.2` | `rxnorm_search`, `rxnorm_get_properties`, `rxnorm_related`, `rxnorm_ndc` |
| openFDA ([cyanheads/openfda-mcp-server](https://github.com/cyanheads/openfda-mcp-server)) → api.fda.gov | `npx -y @cyanheads/openfda-mcp-server@0.7.9` with `MCP_TRANSPORT_TYPE=stdio` | `openfda_drug_profile`, `openfda_search_recalls`, `openfda_search_drug_shortages`, `openfda_get_drug_label`, `openfda_lookup_ndc` |

The drug servers need Node (`npx`), no API keys. Versions are pinned: an unpinned
`npx` picked up a cached openFDA 0.7.6 with only 7 tools (no shortages or
drug_profile); 0.7.9 has 14 and warns it wants Node 24 but runs on Node 22. RxNorm
runs locally rather than through the Pipeworx hosted gateway, so drug look-ups go
straight to NLM and FDA.

```bash
python pharmacy_agent.py            # default: diabetic members' drugs, shortages, recalls since 2025
```

On 2026-09-29 (17 tool calls): 2 members, 3 active drugs (metformin ER 500 mg,
simvastatin 10 mg, acetaminophen 325 mg), no current shortages, and one recall
matching each member's exact RxCUI: D-0292-2025 (metformin ER 500 mg, lot 4260340,
foreign tablets) and D-0471-2025 (acetaminophen 325 mg, lot AEF124004A, cGMP). Both
checked against api.fda.gov. Synthea prescriptions have no NDC or lot, so whether a
member got the recalled lot needs pharmacy claims.

## Fraud investigation demo and difficulty ladder

[`fraud/`](fraud/README.md) has a LangGraph agent that investigates this server's claims
for billing fraud, choosing among the read-only FHIR MCP tools and six claims-analytics
tools, with a React app that shows its reasoning, tool choices and results live
(`fraud/run_server.sh`, http://localhost:8765).

Synthea's claims contain no fraud, so `fraud/seed_fraud.py --level 1-5` plants it at five
difficulty levels, and `fraud/ladder.py` runs the agent on each and scores it by provider.

**Difficulty ladder results (2026-09-30, one run per level, so indicative only):**

| Level | What's planted | Guilty providers found | Schemes described | Innocent providers accused | Tool calls | Time |
|---|---|---:|---:|---:|---:|---:|
| 1 Obvious | upcoding at ~6x peers, a 26-visit day, visits after death, exact duplicates | 2/2 | 4/4 | 0 | 25 | 71 s |
| 2 Subtle | 1.6x upcoding on half a provider's claims, 14 visits in 10 hours, duplicates re-billed a day later, visits 2-3 weeks after death | 2/2 | 3/4 | 0 | 21 | 80 s |
| 3 Spread thin | six existing Synthea providers: one exact duplicate each, or three claims at 2.5x | 5/6 | 5/6 | 0 | 24 | 77 s |
| 4 Unnamed schemes | unbundling, weekly therapy for 26 weeks, phantom patients (no tool covers these) | 2/3 | 2/3 | 0 | 31 | 86 s |
| 5 Clean | nothing | n/a | n/a | **0** | 33 | 70 s |

- **Found without a dedicated tool:** unbundling (one blood count billed as four tests)
  and the weekly therapy.
- **Missed:** the next-day re-billing (level 2), one provider's three 2.5x claims
  (level 3), the phantom patients (level 4).
- **No innocent provider was accused at any level**, including the clean one.
- Levels 1-3 map onto the analytics tools, so 4 and 5 are the fairer tests. The agent
  describes schemes in its own words. About $6 of Claude usage per pass.

Details, caveats and how to run it: [`fraud/README.md`](fraud/README.md).

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

Payer-style questions to try: "find members with type 2 diabetes and their latest
HbA1c", "list the claims for Patient/<id> in the last year and what was paid", "which
providers billed the most encounters".

## Not for real data

This setup has no authentication, no TLS and no audit trail. Use only synthetic
data. Real member or patient data needs a BAA with the AI provider, a security
review, audit logging, and minimum-necessary access scopes.

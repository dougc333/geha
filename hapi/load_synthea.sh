#!/usr/bin/env bash
# Generate synthetic patients with Synthea and load them into the local HAPI server.
#
#   ./load_synthea.sh [patients] [state]      # default: 50 Missouri patients
#
# Synthea runs in a Java container (no local Java needed). The same seed gives the
# same patients every time. Output: synthea/output/fhir/*.json (FHIR R4 transaction
# bundles: Patient, Encounter, Condition, Observation, MedicationRequest, Claim,
# ExplanationOfBenefit, ...). Hospital and practitioner bundles are loaded first,
# because patient bundles reference them.
set -euo pipefail

PATIENTS="${1:-50}"
STATE="${2:-Missouri}"
SEED=42
FHIR="${FHIR_BASE:-http://localhost:8080/fhir}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/synthea/output"

echo "Waiting for HAPI at $FHIR ..."
until curl -sf "$FHIR/metadata" -o /dev/null; do sleep 5; done

rm -rf "$OUT"
echo "Generating $PATIENTS synthetic patients in $STATE (seed $SEED) ..."
docker run --rm -v "$HERE/synthea:/work" -w /work eclipse-temurin:17-jre \
  java -jar synthea-with-dependencies.jar -p "$PATIENTS" -s "$SEED" -cs "$SEED" \
    --exporter.baseDirectory=/work/output \
    --exporter.years_of_history=10 \
    --exporter.fhir.export=true \
    --exporter.hospital.fhir.export=true \
    --exporter.practitioner.fhir.export=true \
    "$STATE" | tail -3

post() {  # POST one transaction bundle; print a short status line
  local code
  code=$(curl -s -o /tmp/hapi_load_response.json -w '%{http_code}' -X POST "$FHIR" \
    -H 'Content-Type: application/fhir+json' --data-binary "@$1")
  if [[ "$code" != 200 ]]; then
    echo "  FAILED $code $(basename "$1"): $(head -c 300 /tmp/hapi_load_response.json)"
    return 1
  fi
  echo "  ok $(basename "$1")"
}

echo "Loading into $FHIR ..."
failed=0
for f in "$OUT"/fhir/hospitalInformation*.json "$OUT"/fhir/practitionerInformation*.json; do
  post "$f" || failed=$((failed + 1))
done
for f in "$OUT"/fhir/*.json; do
  case "$(basename "$f")" in hospitalInformation*|practitionerInformation*) continue ;; esac
  if ! result=$(post "$f"); then echo "$result"; failed=$((failed + 1)); fi   # print failures only
done

echo "Done; failed bundles: $failed"
for type in Patient Encounter Condition Observation MedicationRequest Claim ExplanationOfBenefit Coverage Practitioner Organization; do
  printf '  %-22s %s\n' "$type" "$(curl -s "$FHIR/$type?_summary=count" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("total"))')"
done

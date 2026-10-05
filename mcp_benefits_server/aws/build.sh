#!/bin/zsh
# Assemble the Lambda package in aws/.build: the server code, the one parser it reuses from
# the enrollment chatbot, and only the plan documents the tools read. Paths mirror the repo,
# so tools.py resolves its data exactly as it does locally.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$HERE/.build"
FEDVIP="downloads/dental/fedvip"

rm -rf "$OUT"
mkdir -p "$OUT/mcp_benefits_server/src" "$OUT/dental_enrollment_chatbot/src" \
         "$OUT/$FEDVIP/2026-geha-dental-benefits-guide_pages" \
         "$OUT/$FEDVIP/2026-geha-dental-plan-brochure_pages" "$OUT/downloads/coverage-policies"

cp "$HERE/handler.py" "$HERE/requirements.txt" "$OUT/"
cp "$REPO"/mcp_benefits_server/src/{registry,tools,server}.py "$OUT/mcp_benefits_server/src/"
cp "$REPO/dental_enrollment_chatbot/src/guide_tables.py" "$OUT/dental_enrollment_chatbot/src/"
cp "$REPO/$FEDVIP"/2026-geha-dental-benefits-guide_pages/page-01{0,1}.md \
   "$OUT/$FEDVIP/2026-geha-dental-benefits-guide_pages/"
for page in {20..37}; do
  cp "$REPO/$FEDVIP/2026-geha-dental-plan-brochure_pages/page-0$page.md" \
     "$OUT/$FEDVIP/2026-geha-dental-plan-brochure_pages/"
done
cp "$REPO"/downloads/coverage-policies/geha-coverage-policy-*.docling.md "$OUT/downloads/coverage-policies/"

echo "package: $OUT ($(find "$OUT" -type f | wc -l | tr -d ' ') files, $(du -sh "$OUT" | cut -f1))"

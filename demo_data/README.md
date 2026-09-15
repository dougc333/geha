# Shared synthetic demo data

These small, fabricated fixtures are the common read-only inputs for the
LangGraph and MCP demonstrations:

- `claims.json`: synthetic claim and member identifiers plus plan labels;
- `audit_trails.json`: deterministic simulated claim outcomes and stage notes;
- `public_reference.json`: curated public administrative guidance with URLs.

They contain no real member data and are not authoritative coverage or payment
rules. Keeping the fixtures here avoids coupling the active demos to separate
legacy applications. Tests create equivalent temporary `demo_data/` trees and
must not mutate these checked-in files.

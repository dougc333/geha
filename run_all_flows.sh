#!/usr/bin/env bash
# Run all 9 processing-flow simulations in dependency order.
# Usage: bash run_all_flows.sh
set -e
cd "$(dirname "$0")"

echo "==== GEHA processing-flow simulations ===="
python 01_membership_benefits/simulate_membership.py
python 02_provider_operations/simulate_providers.py
python 03_utilization_management/simulate_utilization.py
python 04_premium_billing/simulate_premium_billing.py
python 05_appeals_disputes/simulate_appeals.py
python 06_payment_integrity/simulate_payment_integrity.py
python 07_care_case_management/simulate_care_management.py
python 08_member_services/simulate_member_services.py
python 09_compliance/simulate_compliance.py
echo "==== all flows complete ===="

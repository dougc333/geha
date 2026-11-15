"""Install the geha_dental domain into a tau2-bench checkout.

    python install.py ~/tau2-bench

Copies the domain code, data and tests into the checkout and registers the domain in
src/tau2/registry.py. Safe to run again: files are overwritten and registration is skipped
if it is already there.
"""

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

IMPORTS = '''from tau2.domains.geha_dental.environment import (
    get_environment as geha_dental_domain_get_environment,
)
from tau2.domains.geha_dental.environment import get_tasks as geha_dental_domain_get_tasks
from tau2.domains.geha_dental.environment import (
    get_tasks_split as geha_dental_domain_get_tasks_split,
)
'''
REGISTER = '''    registry.register_domain(geha_dental_domain_get_environment, "geha_dental")
    registry.register_tasks(
        geha_dental_domain_get_tasks,
        "geha_dental",
        get_task_splits=geha_dental_domain_get_tasks_split,
    )

'''


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1]).expanduser().resolve()
    registry = root / "src/tau2/registry.py"
    if not registry.exists():
        print(f"{root} does not look like a tau2-bench checkout (no src/tau2/registry.py)")
        return 1
    for src, dst in [("domain", "src/tau2/domains/geha_dental"),
                     ("data", "data/tau2/domains/geha_dental"),
                     ("tests", "tests/test_domains/test_geha_dental")]:
        shutil.copytree(HERE / src, root / dst, dirs_exist_ok=True)
        print(f"copied {src}/ -> {dst}/")
    text = registry.read_text()
    if "geha_dental" in text:
        print("registry already has geha_dental")
        return 0
    anchor_import = "from tau2.domains.airline.environment import (\n"
    anchor_register = '    registry.register_domain(airline_domain_get_environment, "airline")'
    if anchor_import not in text or anchor_register not in text:
        print("Could not find where to register the domain; add the lines in README.md by hand.")
        return 1
    text = text.replace(anchor_import, IMPORTS + anchor_import, 1)
    text = text.replace(anchor_register, REGISTER + anchor_register, 1)
    registry.write_text(text)
    print("registered geha_dental in src/tau2/registry.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

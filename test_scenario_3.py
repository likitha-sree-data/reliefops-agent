import json
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path="reliefops/.env")

sys.path.insert(0, "reliefops")
from reliefops.agent import request_approval

INVENTORY_PATH = Path("reliefops/data/inventory.json")

original = json.loads(INVENTORY_PATH.read_text())
print(f"Backed up original inventory: {original}")

try:
    shrunk = dict(original)
    shrunk["water_units"] = 100
    INVENTORY_PATH.write_text(json.dumps(shrunk, indent=2))
    print("Temporarily set water_units to 100")

    result = request_approval("Shelter B")
    status = result.get("action_status")
    passed = status == "PENDING_HUMAN_APPROVAL"

    print(f"[{'PASS' if passed else 'FAIL'}] Scenario 3: Oversized allocation requires approval: action_status={status}")

finally:
    INVENTORY_PATH.write_text(json.dumps(original, indent=2))
    print(f"Restored original inventory: {original}")
    restored = json.loads(INVENTORY_PATH.read_text())
    assert restored == original, "RESTORE FAILED, inventory.json does not match original!"
    print("Restore verified correct.")

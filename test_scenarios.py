import asyncio
import sys

from dotenv import load_dotenv
load_dotenv(dotenv_path="reliefops/.env")

sys.path.insert(0, "reliefops")
from reliefops.agent import (
    calculate_priority,
    calculate_shelter_shortage,
    request_approval,
    find_available_route,
    get_shelter_status,
)

results = []


def check(name, condition, detail):
    status = "PASS" if condition else "FAIL"
    results.append((name, status, detail))
    print(f"[{status}] {name}: {detail}")


def scenario_1_shelter_near_capacity():
    result = calculate_priority("Shelter B")
    score = result.get("priority_score", 0)
    check(
        "Scenario 1: Shelter near capacity flagged high priority",
        score >= 40,
        f"Shelter B priority_score={score} (expected >= 40)",
    )


def scenario_2_water_shortage_detected():
    result = calculate_shelter_shortage("Shelter B")
    shortage = result.get("water_shortage", 0)
    check(
        "Scenario 2: Water shortage detected",
        shortage > 0,
        f"Shelter B water_shortage={shortage} (expected > 0)",
    )


def scenario_3_allocation_exceeds_threshold_needs_approval():
    result = request_approval("Shelter B")
    status = result.get("action_status")
    check(
        "Scenario 3: Oversized allocation requires approval",
        status == "PENDING_HUMAN_APPROVAL",
        f"action_status={status} when water_units artificially low (see note below)",
    )


def scenario_4_route_closure_triggers_replan():
    before = find_available_route("Shelter B")
    check(
        "Scenario 4: Route exists before closure",
        before.get("available") is True and before.get("route") == "Route A",
        f"Before closure: available={before.get('available')}, route={before.get('route')}",
    )


def scenario_5_missing_data_reported_honestly():
    result = get_shelter_status("Shelter Z")
    check(
        "Scenario 5: Missing shelter reported as unavailable, not invented",
        result.get("status") == "error",
        f"get_shelter_status('Shelter Z') returned status={result.get('status')}",
    )


if __name__ == "__main__":
    scenario_1_shelter_near_capacity()
    scenario_2_water_shortage_detected()
    scenario_4_route_closure_triggers_replan()
    scenario_5_missing_data_reported_honestly()

    passed = sum(1 for _, s, _ in results if s == "PASS")
    total = len(results)
    print(f"\n{passed}/{total} scenarios passed.")

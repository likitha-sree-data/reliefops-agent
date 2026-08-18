import json
import os
from pathlib import Path

from google.adk.agents import Agent
from google.cloud import firestore

DATA_DIR = Path(__file__).parent / "data"

MIN_WATER_PER_PERSON = 1
MIN_MEALS_PER_PERSON = 1
APPROVAL_THRESHOLD_PERCENT = 0.20

TASKS_COLLECTION = "tasks"
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "reliefops-agent")

RESOURCE_ALIASES = {
    "water": "water_units",
    "water_units": "water_units",
    "meal": "meal_units",
    "meals": "meal_units",
    "meal_units": "meal_units",
    "blanket": "blankets",
    "blankets": "blankets",
    "medical_kit": "medical_kits",
    "medical_kits": "medical_kits",
    "medical": "medical_kits",
}


def _load_shelters() -> dict:
    with open(DATA_DIR / "shelters.json") as f:
        return json.load(f)


def _load_inventory() -> dict:
    with open(DATA_DIR / "inventory.json") as f:
        return json.load(f)


ROUTES_COLLECTION = "routes"


def _load_routes() -> list:
    db = _firestore_client()
    docs = db.collection(ROUTES_COLLECTION).stream()
    return [doc.to_dict() for doc in docs]


def _firestore_client() -> firestore.Client:
    return firestore.Client(project=GCP_PROJECT)


def _load_tasks() -> list:
    db = _firestore_client()
    docs = db.collection(TASKS_COLLECTION).stream()
    tasks = [doc.to_dict() for doc in docs]
    tasks.sort(key=lambda t: t.get("task_id", ""))
    return tasks


def _save_task(task: dict) -> None:
    db = _firestore_client()
    db.collection(TASKS_COLLECTION).document(task["task_id"]).set(task)


def _next_task_id() -> str:
    db = _firestore_client()
    count = sum(1 for _ in db.collection(TASKS_COLLECTION).stream())
    return f"TASK-{count + 1:03d}"


def _find_shelter(shelters: dict, shelter_name: str):
    normalized = shelter_name.strip().lower()
    for name, data in shelters.items():
        if name.lower() == normalized:
            return name, data
    return None, None


def _shortage_calc(shelter: dict) -> dict:
    occupancy = shelter["occupancy"]
    water_needed = occupancy * MIN_WATER_PER_PERSON
    meals_needed = occupancy * MIN_MEALS_PER_PERSON
    water_shortage = max(0, water_needed - shelter["water_units"])
    meal_shortage = max(0, meals_needed - shelter["meal_units"])
    return {
        "occupancy": occupancy,
        "water_units_available": shelter["water_units"],
        "water_units_needed": water_needed,
        "water_shortage": water_shortage,
        "meal_units_available": shelter["meal_units"],
        "meal_units_needed": meals_needed,
        "meal_shortage": meal_shortage,
        "has_shortage": water_shortage > 0 or meal_shortage > 0,
    }


def _accessibility_score(canonical_shelter_name: str) -> dict:
    routes = _load_routes()
    matching = [r for r in routes if r["destination"].lower() == canonical_shelter_name.lower()]

    if not matching:
        return {"score": 0, "data_available": False, "matching_routes": []}

    statuses = [r["status"].lower() for r in matching]
    if "open" in statuses:
        score = 0
    elif "restricted" in statuses:
        score = 50
    else:
        score = 100

    return {"score": score, "data_available": True, "matching_routes": matching}


def get_shelter_status(shelter_name: str) -> dict:
    """Returns the current operational status of a single named disaster shelter."""
    if False: print(f"[TOOL CALLED] get_shelter_status(shelter_name={shelter_name!r})")
    shelters = _load_shelters()
    canonical_name, shelter = _find_shelter(shelters, shelter_name)
    if shelter is None:
        return {"status": "error", "message": f"No data found for {shelter_name}"}
    return {"status": "success", "shelter": canonical_name, **shelter}


def get_shelters() -> dict:
    """Returns operational status for ALL disaster shelters at once, for comparing shelters against each other."""
    if False: print("[TOOL CALLED] get_shelters()")
    shelters = _load_shelters()
    return {"status": "success", "shelters": shelters}


def calculate_shelter_shortage(shelter_name: str) -> dict:
    """Deterministically calculates the water and meal shortage for a named shelter, based on occupancy."""
    if False: print(f"[TOOL CALLED] calculate_shelter_shortage(shelter_name={shelter_name!r})")
    shelters = _load_shelters()
    canonical_name, shelter = _find_shelter(shelters, shelter_name)
    if shelter is None:
        return {"status": "error", "message": f"No data found for {shelter_name}"}
    return {"status": "success", "shelter": canonical_name, **_shortage_calc(shelter)}


def get_inventory() -> dict:
    """Returns the current warehouse inventory levels for all resource types."""
    if False: print("[TOOL CALLED] get_inventory()")
    inventory = _load_inventory()
    return {"status": "success", "inventory": inventory}


def check_resource_availability(resource_type: str, amount: int) -> dict:
    """Deterministically checks whether the warehouse has enough of a given resource to cover a requested amount."""
    if False: print(f"[TOOL CALLED] check_resource_availability(resource_type={resource_type!r}, amount={amount!r})")
    normalized = resource_type.strip().lower()
    key = RESOURCE_ALIASES.get(normalized)
    if key is None:
        return {"status": "error", "message": f"Unknown resource type '{resource_type}'. Valid types: water, meals, blankets, medical_kits"}
    inventory = _load_inventory()
    available = inventory.get(key, 0)
    shortfall = max(0, amount - available)
    return {
        "status": "success",
        "resource_type": key,
        "requested_amount": amount,
        "available_amount": available,
        "is_available": shortfall == 0,
        "shortfall": shortfall,
    }


def get_routes() -> dict:
    """Returns the status of ALL known transportation routes."""
    if False: print("[TOOL CALLED] get_routes()")
    routes = _load_routes()
    return {"status": "success", "routes": routes}


def get_route_status(route_name: str) -> dict:
    """Returns the status of a single named route, e.g. 'Route A'."""
    if False: print(f"[TOOL CALLED] get_route_status(route_name={route_name!r})")
    routes = _load_routes()
    normalized = route_name.strip().lower()
    for route in routes:
        if route["route"].lower() == normalized:
            return {"status": "success", **route}
    return {"status": "error", "message": f"No data found for {route_name}"}


def find_available_route(destination: str) -> dict:
    """Deterministically finds the first OPEN route to a named destination."""
    if False: print(f"[TOOL CALLED] find_available_route(destination={destination!r})")
    routes = _load_routes()
    normalized = destination.strip().lower()
    matching = [r for r in routes if r["destination"].lower() == normalized]
    if not matching:
        return {"status": "error", "message": f"No routes found for destination {destination}"}
    open_routes = [r for r in matching if r["status"].lower() == "open"]
    if open_routes:
        return {"status": "success", "available": True, "route": open_routes[0]["route"], "destination": destination, "all_routes_checked": matching}
    return {"status": "success", "available": False, "message": f"No open route currently exists to {destination}", "all_routes_checked": matching}


def calculate_priority(shelter_name: str) -> dict:
    """Deterministically calculates a 0-100 priority score for a named shelter using a fixed weighted formula."""
    if False: print(f"[TOOL CALLED] calculate_priority(shelter_name={shelter_name!r})")
    shelters = _load_shelters()
    canonical_name, shelter = _find_shelter(shelters, shelter_name)
    if shelter is None:
        return {"status": "error", "message": f"No data found for {shelter_name}"}
    capacity = shelter["capacity"]
    occupancy_score = min(100.0, (shelter["occupancy"] / capacity) * 100) if capacity > 0 else 0.0
    shortage = _shortage_calc(shelter)
    water_score = min(100.0, (shortage["water_shortage"] / shortage["water_units_needed"]) * 100) if shortage["water_units_needed"] > 0 else 0.0
    meal_score = min(100.0, (shortage["meal_shortage"] / shortage["meal_units_needed"]) * 100) if shortage["meal_units_needed"] > 0 else 0.0
    medical_score = 0.0
    access = _accessibility_score(canonical_name)
    access_score = access["score"]
    priority_score = (0.35 * occupancy_score + 0.25 * water_score + 0.20 * meal_score + 0.10 * medical_score + 0.10 * access_score)
    return {
        "status": "success",
        "shelter": canonical_name,
        "priority_score": round(priority_score, 1),
        "breakdown": {
            "occupancy_pressure": {"score": round(occupancy_score, 1), "weight": 0.35},
            "water_shortage": {"score": round(water_score, 1), "weight": 0.25},
            "food_shortage": {"score": round(meal_score, 1), "weight": 0.20},
            "medical_risk": {"score": medical_score, "weight": 0.10, "note": "no per-shelter medical data source yet"},
            "accessibility_risk": {"score": access_score, "weight": 0.10, "data_available": access["data_available"]},
        },
    }


def create_allocation_plan(shelter_name: str) -> dict:
    """Deterministically assembles a resource allocation plan for a named shelter."""
    if False: print(f"[TOOL CALLED] create_allocation_plan(shelter_name={shelter_name!r})")
    shelters = _load_shelters()
    canonical_name, shelter = _find_shelter(shelters, shelter_name)
    if shelter is None:
        return {"status": "error", "message": f"No data found for {shelter_name}"}
    shortage = _shortage_calc(shelter)
    inventory = _load_inventory()
    water_shortfall = max(0, shortage["water_shortage"] - inventory.get("water_units", 0))
    meal_shortfall = max(0, shortage["meal_shortage"] - inventory.get("meal_units", 0))
    water_to_send = shortage["water_shortage"] - water_shortfall
    meals_to_send = shortage["meal_shortage"] - meal_shortfall
    route_check = find_available_route(canonical_name)
    return {
        "status": "success",
        "shelter": canonical_name,
        "recommended_water_units": water_to_send,
        "recommended_meal_units": meals_to_send,
        "warehouse_water_shortfall": water_shortfall,
        "warehouse_meal_shortfall": meal_shortfall,
        "fully_covered": water_shortfall == 0 and meal_shortfall == 0,
        "route_available": route_check.get("available", False),
        "recommended_route": route_check.get("route"),
        "route_details": route_check,
    }


def requires_human_approval(shelter_name: str) -> dict:
    """Internal helper, not exposed to the model as a tool."""
    plan = create_allocation_plan(shelter_name)
    if plan["status"] != "success":
        return plan

    inventory = _load_inventory()
    total_water = inventory.get("water_units", 0)
    total_meals = inventory.get("meal_units", 0)

    reasons = []

    if total_water > 0 and plan["recommended_water_units"] / total_water > APPROVAL_THRESHOLD_PERCENT:
        reasons.append(f"Water allocation ({plan['recommended_water_units']}) exceeds {int(APPROVAL_THRESHOLD_PERCENT*100)}% of total warehouse water stock ({total_water}).")
    if total_meals > 0 and plan["recommended_meal_units"] / total_meals > APPROVAL_THRESHOLD_PERCENT:
        reasons.append(f"Meal allocation ({plan['recommended_meal_units']}) exceeds {int(APPROVAL_THRESHOLD_PERCENT*100)}% of total warehouse meal stock ({total_meals}).")
    if not plan["route_available"]:
        reasons.append("No open route currently exists to this shelter, route risk is critical.")
    if not plan["fully_covered"]:
        reasons.append("Warehouse cannot fully cover this shelter's shortage, allocation would be partial.")

    approval_required = len(reasons) > 0

    return {
        "status": "success",
        "shelter": plan["shelter"],
        "approval_required": approval_required,
        "reasons": reasons if approval_required else ["Allocation is within policy limits, fully covered, and has an open route."],
        "plan": plan,
    }


def request_approval(shelter_name: str) -> dict:
    """Deterministically checks a shelter's allocation plan against approval policy and either marks it auto-approved or pending human approval."""
    if False: print(f"[TOOL CALLED] request_approval(shelter_name={shelter_name!r})")

    check = requires_human_approval(shelter_name)
    if check["status"] != "success":
        return check

    status_label = "PENDING_HUMAN_APPROVAL" if check["approval_required"] else "AUTO_APPROVED_WITHIN_POLICY"

    return {
        "status": "success",
        "shelter": check["shelter"],
        "action_status": status_label,
        "reasons": check["reasons"],
        "plan": check["plan"],
    }


def create_task(shelter_name: str) -> dict:
    """Creates and persists an operational task recording a shelter's allocation plan, priority, and approval status. Task records are stored in Firestore, shared across all instances."""
    if False: print(f"[TOOL CALLED] create_task(shelter_name={shelter_name!r})")

    approval = request_approval(shelter_name)
    if approval["status"] != "success":
        return approval

    priority = calculate_priority(approval["shelter"])
    priority_score = priority.get("priority_score") if priority.get("status") == "success" else None

    task_id = _next_task_id()

    task = {
        "task_id": task_id,
        "shelter": approval["shelter"],
        "action": "deliver_supplies",
        "recommended_water_units": approval["plan"]["recommended_water_units"],
        "recommended_meal_units": approval["plan"]["recommended_meal_units"],
        "recommended_route": approval["plan"]["recommended_route"],
        "priority_score": priority_score,
        "status": approval["action_status"],
        "reasons": approval["reasons"],
    }

    _save_task(task)

    return {"status": "success", "task": task}


def update_task(task_id: str, new_status: str) -> dict:
    """Updates the status field of an existing task by task_id. Reads and writes directly to Firestore, so this is visible to every instance immediately."""
    if False: print(f"[TOOL CALLED] update_task(task_id={task_id!r}, new_status={new_status!r})")

    db = _firestore_client()
    doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
    doc = doc_ref.get()

    if not doc.exists:
        return {"status": "error", "message": f"No task found with id {task_id}"}

    task = doc.to_dict()
    old_status = task["status"]
    task["status"] = new_status
    doc_ref.set(task)

    return {
        "status": "success",
        "task_id": task_id,
        "old_status": old_status,
        "new_status": new_status,
        "task": task,
    }


root_agent = Agent(
    name="reliefops_agent",
    model="gemini-3.5-flash",
    description="An autonomous disaster-response operations coordination agent.",
    instruction="""
You are ReliefOps, an emergency operations coordination agent.

Your job is to inspect operational data using the tools provided to you.

Rules:
1. Always use tools when answering questions about shelter, inventory, route, or task status.
2. Never invent values or calculate anything yourself, always call the matching tool.
3. If data is unavailable, explicitly say that the data is unavailable, don't guess.
4. Identify operational risks clearly and concisely.
5. Do not claim that an action has been executed unless a tool confirms it. A task with status PENDING_HUMAN_APPROVAL has NOT been executed, it is waiting.
6. Tool selection: single named shelter status -> get_shelter_status. Comparing shelters -> get_shelters. Shortage at a shelter -> calculate_shelter_shortage. Warehouse stock -> get_inventory. Whether enough of a resource exists -> check_resource_availability. All routes -> get_routes. One named route -> get_route_status. Whether a usable route exists -> find_available_route. Which shelter needs help first -> calculate_priority. Recommended allocation -> create_allocation_plan. Whether an allocation is approved to proceed or must pause -> request_approval. Turning a recommendation into a tracked task -> create_task. Changing an existing task's status by its task_id -> update_task.
7. Always explain results using their breakdown or reasons, don't just state a number or label.
8. create_task is how work actually gets tracked. If a user asks you to "create a task", "dispatch", "send supplies to", or "act on" a shelter's plan, use create_task, not just create_allocation_plan.
""",
    tools=[
        get_shelter_status,
        get_shelters,
        calculate_shelter_shortage,
        get_inventory,
        check_resource_availability,
        get_routes,
        get_route_status,
        find_available_route,
        calculate_priority,
        create_allocation_plan,
        request_approval,
        create_task,
        update_task,
    ],
)

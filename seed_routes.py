from google.cloud import firestore

db = firestore.Client(project="reliefops-agent")

routes = [
    {"route": "Route A", "destination": "Shelter B", "status": "open"},
    {"route": "Route B", "destination": "Shelter B", "status": "flooded"},
    {"route": "Route C", "destination": "Shelter B", "status": "restricted"},
]

for r in routes:
    db.collection("routes").document(r["route"]).set(r)
    print(f"Seeded {r['route']}: {r['status']}")

extra_routes = [
    {"route": "Route D", "destination": "Shelter A", "status": "open"},
    {"route": "Route E", "destination": "Shelter C", "status": "open"},
]

for r in extra_routes:
    db.collection("routes").document(r["route"]).set(r)
    print(f"Seeded {r['route']}: {r['status']}")

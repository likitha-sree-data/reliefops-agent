import asyncio
import json
import sys

from dotenv import load_dotenv

load_dotenv(dotenv_path="reliefops/.env")

from google.cloud import firestore, pubsub_v1
from google.adk.runners import InMemoryRunner
from google.genai import types

PROJECT_ID = "reliefops-agent"
SUBSCRIPTION_ID = "reliefops-events-sub"

sys.path.insert(0, "reliefops")
from reliefops.agent import root_agent

db = firestore.Client(project=PROJECT_ID)
subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)


def apply_route_event(event: dict) -> str:
    """Directly updates Firestore based on the event, then returns a plain-language description for the agent to reason about."""
    if event.get("event_type") == "road_closure":
        route_name = event["route"]
        doc_ref = db.collection("routes").document(route_name)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["status"] = "flooded"
            doc_ref.set(data)
            return (
                f"URGENT OPERATIONAL UPDATE: {route_name} has just been closed "
                f"due to a road closure event. It is no longer usable. "
                f"Check whether any shelter that depended on {route_name} still has "
                f"a usable route, and if not, recommend what should happen next."
            )
    return f"Received an event I don't know how to handle: {json.dumps(event)}"


async def run_agent_with_message(message_text: str):
    runner = InMemoryRunner(agent=root_agent, app_name="reliefops_pubsub")
    session = await runner.session_service.create_session(
        app_name="reliefops_pubsub", user_id="pubsub-listener"
    )
    content = types.Content(role="user", parts=[types.Part(text=message_text)])

    async for event in runner.run_async(
        user_id="pubsub-listener", session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[AGENT] {part.text}")


def callback(message):
    print(f"\n[PUBSUB] Received: {message.data.decode('utf-8')}")
    event = json.loads(message.data.decode("utf-8"))
    prompt = apply_route_event(event)
    print(f"[PUBSUB] Prompting agent with: {prompt}\n")

    asyncio.run(run_agent_with_message(prompt))

    message.ack()
    print("[PUBSUB] Acked.\n")


print(f"Listening on {subscription_path}... (Ctrl+C to stop)")
streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

try:
    streaming_pull_future.result()
except KeyboardInterrupt:
    streaming_pull_future.cancel()
    print("\nListener stopped.")

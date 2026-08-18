from google import genai

client = genai.Client(
    vertexai=True,
    project="reliefops-agent",
    location="global"
)

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="""
You are helping build ReliefOps, an autonomous disaster-response operations agent.

A flood has affected a county.
Shelter B has capacity for 300 people and currently has 292 occupants.
It has 180 units of water and 240 meals remaining.

In two sentences, identify the main operational risk.
"""
)

print(response.text)


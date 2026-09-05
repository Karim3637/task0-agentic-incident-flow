import os
import json
import requests

from fastapi import FastAPI, BackgroundTasks
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, ConfigDict, Field


load_dotenv()

app = FastAPI()


# =========================
# Incident Payload
# =========================

class IncidentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_sys_id: str
    number: str
    short_description: str
    description: str
    priority: int = Field(ge=1, le=5)


# =========================
# Gemini
# =========================

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# =========================
# ServiceNow
# =========================

SERVICENOW_INSTANCE_URL = os.getenv("SERVICENOW_INSTANCE_URL")
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")


# =========================
# Duplicate Protection
# =========================

processed_incidents = set()


# =========================
# Gemini Decision
# =========================

def get_gemini_decision(data):

    with open("prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()

    prompt = prompt.replace(
        "{number}",
        str(data.number)
    )

    prompt = prompt.replace(
        "{short_description}",
        str(data.short_description)
    )

    prompt = prompt.replace(
        "{description}",
        str(data.description)
    )

    prompt = prompt.replace(
        "{priority}",
        str(data.priority)
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt
    )

    print("Gemini response:")
    print(response.text)

    text = response.text.strip()

    # Remove Markdown code fences if Gemini adds them
    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    result = json.loads(text)

    # Validate decision
    if result.get("decision") not in [
        "respond",
        "ask",
        "escalate"
    ]:
        raise ValueError("Invalid Gemini decision")

    # Validate required Gemini fields
    if set(result.keys()) != {"decision", "message"}:
        raise ValueError(
            "Gemini response must contain exactly "
            "'decision' and 'message'"
        )

    if not isinstance(result["message"], str):
        raise ValueError("Gemini message must be a string")

    return result


# =========================
# Update ServiceNow
# =========================

def update_servicenow(
    incident_sys_id,
    decision,
    message
):

    print("Calling ServiceNow")

    url = (
        f"{SERVICENOW_INSTANCE_URL}"
        f"/api/now/table/incident/{incident_sys_id}"
    )

    if decision == "respond":

        payload = {
            "work_notes": message,
            "state": "6",
            "close_notes": message,
            "close_code": "Solution provided"
        }

    elif decision == "ask":

        payload = {
            "comments": message
        }

    else:

        payload = {
            "work_notes": message
        }

    response = requests.patch(
        url,
        auth=(
            SERVICENOW_USERNAME,
            SERVICENOW_PASSWORD
        ),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        json=payload,
        timeout=15
    )

    print(
        "ServiceNow status code:",
        response.status_code
    )

    print(
        "ServiceNow response body:",
        response.text
    )

    response.raise_for_status()

    print("ServiceNow updated successfully")


# =========================
# Process Incident
# =========================

def process_incident(data: IncidentPayload):

    incident_id = data.incident_sys_id

    try:

        print("Starting incident processing")

        result = get_gemini_decision(data)

        print("Gemini finished")

        decision = result["decision"]
        message = result["message"]

        print("Decision:", decision)
        print("Message:", message)

        update_servicenow(
            incident_id,
            decision,
            message
        )

        # Mark as successfully processed
        processed_incidents.add(incident_id)

        print("Incident marked as processed")

    except Exception as e:

        print("ERROR:", repr(e))


# =========================
# Webhook
# =========================

@app.post("/webhook", status_code=202)
async def webhook(
    data: IncidentPayload,
    background_tasks: BackgroundTasks
):

    incident_id = data.incident_sys_id

    # Already completed
    if incident_id in processed_incidents:

        return {
            "status": "already_processed",
            "incident_sys_id": incident_id
        }

    print("Received incident:")
    print(data.model_dump())

    # Run slow processing in background
    background_tasks.add_task(
        process_incident,
        data
    )

    # Return immediately
    return {
        "status": "accepted",
        "incident_sys_id": incident_id
    }
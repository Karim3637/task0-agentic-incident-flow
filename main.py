import os
import json
import requests

from fastapi import FastAPI, BackgroundTasks
from dotenv import load_dotenv
from google import genai


load_dotenv()

app = FastAPI()


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
# Processed incidents
# =========================

processed_incidents = set()


# =========================
# Gemini decision
# =========================

def get_gemini_decision(data):

    # Read prompt
    with open("prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()

    # Put incident data inside the prompt
    prompt = prompt.replace(
        "{number}",
        str(data.get("number", ""))
    )

    prompt = prompt.replace(
        "{short_description}",
        str(data.get("short_description", ""))
    )

    prompt = prompt.replace(
        "{description}",
        str(data.get("description") or "")
    )

    prompt = prompt.replace(
        "{priority}",
        str(data.get("priority", ""))
    )

    # Ask Gemini
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    print("Gemini response:")
    print(response.text)

    # Remove Markdown code fences if Gemini adds them
    text = response.text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    # Convert Gemini JSON to Python dictionary
    result = json.loads(text)

    # Check decision
    if result.get("decision") not in [
        "respond",
        "ask",
        "escalate"
    ]:
        raise ValueError("Invalid Gemini decision")

    return result


# =========================
# Update ServiceNow
# =========================

def update_servicenow(incident_sys_id, decision, message):

    print("3 - Calling ServiceNow")

    # Same Incident URL
    url = (
        f"{SERVICENOW_INSTANCE_URL}"
        f"/api/now/table/incident/{incident_sys_id}"
    )

    # Data to write back
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


    # PATCH ServiceNow
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

    print("ServiceNow status code:", response.status_code)
    print("ServiceNow response body:", response.text)

    response.raise_for_status()

    print("ServiceNow updated successfully")


# =========================
# Process incident
# =========================

def process_incident(data):

    try:

        # Ask Gemini
        result = get_gemini_decision(data)

        print("2 - Gemini finished")

        decision = result["decision"]
        message = result["message"]

        print("Decision:", decision)
        print("Message:", message)

        # Update same Incident
        update_servicenow(
            data["incident_sys_id"],
            decision,
            message
        )

        # Mark as processed
        processed_incidents.add(
            data["incident_sys_id"]
        )

    except Exception as e:

        print("ERROR:", repr(e))


# =========================
# Webhook
# =========================

@app.post("/webhook")
async def webhook(
    data: dict,
    background_tasks: BackgroundTasks
):

    # Basic validation
    if not data.get("incident_sys_id"):

        return {
            "status": "error",
            "message": "Missing incident_sys_id"
        }

    incident_id = data["incident_sys_id"]

    # Don't process the same Incident twice
    if incident_id in processed_incidents:

        return {
            "status": "already_processed",
            "incident_sys_id": incident_id
        }

    print("Received incident:")
    print(data)

    # Run Gemini + ServiceNow in background
    background_tasks.add_task(
        process_incident,
        data
    )

    # Respond immediately
    return {
        "status": "accepted",
        "incident_sys_id": incident_id
    }
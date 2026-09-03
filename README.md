\# Agentic Incident Flow



\## Overview



An AI-powered incident automation flow connecting ServiceNow with a local FastAPI service and Gemini API.



\### Flow



ServiceNow Incident  

→ Business Rule  

→ ngrok  

→ FastAPI  

→ Gemini  

→ ServiceNow Update



\## Technologies



\- ServiceNow

\- Python

\- FastAPI

\- Gemini API

\- ngrok



\## Setup



1\. Clone the repository.

2\. Create a Python virtual environment.

3\. Install dependencies:



```bash

pip install -r requirements.txt

Create a .env file using .env.example.

Start the FastAPI server:

.venv\\Scripts\\python.exe -m uvicorn main:app --reload --port 8000

Start ngrok:

ngrok http 8000

Configure the ServiceNow Business Rule with the ngrok webhook URL.

AI Decisions



Gemini returns one of three decisions:



respond — provide a solution and resolve the incident.

ask — request additional information through a customer-visible comment.

escalate — add a work note for further investigation.



The AI uses only the five provided Knowledge Base articles.



Environment Variables

GEMINI\_API\_KEY=

SERVICENOW\_INSTANCE\_URL=

SERVICENOW\_USERNAME=

SERVICENOW\_PASSWORD=



Sensitive credentials are stored in .env and are excluded from Git using .gitignore.





Create an Incident in ServiceNow and verify that:



The Business Rule sends the incident to FastAPI.

Gemini makes a decision.

The same incident is updated in ServiceNow


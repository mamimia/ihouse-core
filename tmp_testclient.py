import os
from dotenv import load_dotenv
load_dotenv()

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

from api.auth import jwt_auth
app.dependency_overrides[jwt_auth] = lambda: "tenant_mamimia_staging"

task_id = "6688f6ee75ae38f6"
payload = {"notes": "Check-in completed via wizard"}

print("Hitting PATCH /worker/tasks/{task_id}/complete")
response = client.patch(f"/worker/tasks/{task_id}/complete", json=payload)

print(f"STATUS: {response.status_code}")
print(f"RESPONSE JSON: {response.json()}")

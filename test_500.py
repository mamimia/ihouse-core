import requests
import json
import traceback

try:
    r = requests.post("http://localhost:8000/auth/login", json={"tenant_id": "test_tenant", "secret": "valid_secret_123"})
    if r.status_code == 200:
        token = r.json().get("token")
        if not token:
            print("No token in response:", r.text)
            exit(1)
            
        r2 = requests.get("http://localhost:8000/worker/tasks", headers={"Authorization": f"Bearer {token}"})
        print(f"Status: {r2.status_code}")
        print(f"Body: {r2.text}")
    else:
        print("Login failed:", r.status_code, r.text)
except Exception as e:
    traceback.print_exc()

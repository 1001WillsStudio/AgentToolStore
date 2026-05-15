from fastapi.testclient import TestClient
from app.main import app
from app.database import create_db_and_tables
import os

# Ensure we use a test DB file (or clean it)
if os.path.exists("database.db"):
    os.remove("database.db")

# Explicitly create tables for testing
create_db_and_tables()

client = TestClient(app)

def test_flow():
    # 1. Register
    print("Testing Registration...")
    reg_resp = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    })
    if reg_resp.status_code != 200:
        print(f"Register Failed: {reg_resp.text}")
    assert reg_resp.status_code == 200
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Publish Tool
    print("Testing Publish...")
    tool_def = {
        "name": "my-test-tool",
        "type": "api",
        "description": "A test tool",
        "endpoint": "http://example.com",
        "schema": {}
    }
    
    pub_resp = client.post("/publish", json=tool_def, headers=headers)
    if pub_resp.status_code != 200:
        print(f"Publish Failed: {pub_resp.text}")
    assert pub_resp.status_code == 200
    assert pub_resp.json()["success"] is True
    
    # 3. Get Index
    print("Testing Index...")
    idx_resp = client.get("/index.json")
    assert idx_resp.status_code == 200
    tools = idx_resp.json()
    assert len(tools) == 1
    assert tools[0]["name"] == "my-test-tool"
    assert tools[0]["owner"] == "testuser"
    
    print("Server Test Passed!")

if __name__ == "__main__":
    test_flow()

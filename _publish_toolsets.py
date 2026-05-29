#!/usr/bin/env python3
"""Publish ALL toolsets to the ToolStore registry."""
import sys, json, requests
sys.path.insert(0, 'client/src')
from toolstore.toolset_manager import ToolsetDefinition
from pathlib import Path

BASE = "https://mrw33554432-agenttoolstore.hf.space"
resp = requests.post(f"{BASE}/auth/register", json={"username": "pub_all", "password": "all999"})
TOKEN = resp.json()["access_token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Auto-discover all toolset dirs
ALL = sorted(d.name for d in Path("toolsets").iterdir() if d.is_dir())

ok = fail = 0
for name in ALL:
    td = ToolsetDefinition(f"toolsets/{name}")
    if not td.load() or not td.functions:
        print(f"❌ {name}: validation failed")
        fail += 1
        continue

    with open(f"toolsets/{name}/toolset.py") as f:
        code = f.read()
    try:
        with open(f"toolsets/{name}/doc.md") as f:
            doc = f.read()
    except FileNotFoundError:
        doc = ""

    payload = {
        "name": name, "type": "toolset", "version": "1.0.0",
        "description": doc.split("\n")[0].lstrip("#").strip()[:200] if doc else name,
        "doc": doc, "code": code,
        "bindings": td.functions,
    }

    resp = requests.post(f"{BASE}/publish", json=payload, headers=HEADERS, timeout=30)
    try:
        result = resp.json()
        if result.get("success"):
            ok += 1
            print(f"✅ {name}")
        else:
            detail = str(result.get("detail", ""))[:60]
            print(f"⚠️ {name}: {detail}")
    except Exception:
        print(f"❌ {name}: empty ({resp.status_code})")

print(f"\nDone: {ok} published")

#!/usr/bin/env python3
"""Publish all 8 toolsets to the ToolStore registry."""
import sys, json, requests
sys.path.insert(0, 'client/src')
from toolstore.toolset_manager import ToolsetDefinition

BASE = "https://mrw33554432-agenttoolstore.hf.space"

# Get token
resp = requests.post(f"{BASE}/auth/register", json={"username": "pub_batch", "password": "batch789"})
TOKEN = resp.json()["access_token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

ALL = [
    "text-transform", "file-verify", "xlsx-toolkit", "pdf-toolkit",
    "docx-toolkit", "pptx-toolkit", "text-gen", "batch-ops",
    "calc-toolkit",
]

ok = fail = 0
for name in ALL:
    td = ToolsetDefinition(f"toolsets/{name}")
    ok_load = td.load()
    if not ok_load or not td.functions:
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

    reqs = []
    try:
        with open(f"toolsets/{name}/requirements.txt") as f:
            reqs = [r.strip() for r in f.read().splitlines() if r.strip() and not r.startswith("#")]
    except FileNotFoundError:
        pass

    payload = {
        "name": name, "type": "toolset", "version": "1.0.0",
        "description": doc.split("\n")[0].lstrip("#").strip() if doc else name,
        "doc": doc, "code": code,
        "bindings": td.functions,
    }
    if reqs:
        payload["requirements"] = reqs

    resp = requests.post(f"{BASE}/publish", json=payload, headers=HEADERS, timeout=30)
    try:
        result = resp.json()
        if result.get("success"):
            ok += 1
            print(f"✅ {name} — {len(td.functions)} functions: {list(td.functions.keys())}")
        else:
            fail += 1
            print(f"❌ {name}: {result}")
    except Exception:
        fail += 1
        print(f"❌ {name}: empty response")

print(f"\nDone: {ok} published, {fail} failed")

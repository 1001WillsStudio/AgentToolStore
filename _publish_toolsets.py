#!/usr/bin/env python3
"""Publish all 4 toolsets — each as ONE entry with bindings containing all functions."""
import sys, json
sys.path.insert(0, 'client/src')
from toolstore.toolset_manager import ToolsetDefinition
import requests

BASE = "https://mrw33554432-agenttoolstore.hf.space"

# Get fresh token
resp = requests.post(f"{BASE}/auth/register", json={"username": "pub_admin", "password": "admin123"})
TOKEN = resp.json()["access_token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

TOOLSETS = ["text-transform", "file-verify", "xlsx-toolkit", "pdf-toolkit"]

for name in TOOLSETS:
    td = ToolsetDefinition(f"toolsets/{name}")
    ok = td.load()
    if not ok:
        print(f"❌ {name}: validation failed — {td._errors}")
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

    # SINGLE payload per toolset — name is the directory name
    payload = {
        "name": name,           # "xlsx-toolkit", not individual functions
        "type": "toolset",
        "version": "1.0.0",
        "description": doc.split("\n")[0].lstrip("#").strip() if doc else name,
        "doc": doc,
        "code": code,
        "bindings": td.functions,  # all functions nested inside
    }
    if reqs:
        payload["requirements"] = reqs

    resp = requests.post(f"{BASE}/publish", json=payload, headers=HEADERS, timeout=30)
    try:
        result = resp.json()
        if result.get("success"):
            print(f"✅ {name} — {len(td.functions)} functions: {list(td.functions.keys())}")
        else:
            print(f"❌ {name}: {resp.status_code} {result}")
    except Exception:
        print(f"❌ {name}: {resp.status_code} (empty response)")

print("\nDone!")

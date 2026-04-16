"""Speichert data.json in einen GitHub Gist."""
import os
import json
import urllib.request

GIST_ID = os.environ.get("GIST_ID", "")
GIST_TOKEN = os.environ.get("GIST_TOKEN", "")

if not GIST_ID or not GIST_TOKEN:
    print("Keine Gist-Credentials – Daten werden nicht gespeichert")
else:
    with open("data.json", "r", encoding="utf-8") as f:
        content = f.read()

    payload = json.dumps({
        "files": {
            "data.json": {"content": content}
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        data=payload,
        method="PATCH",
        headers={
            "Authorization": f"token {GIST_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    with urllib.request.urlopen(req) as resp:
        print(f"✅ data.json in Gist gespeichert (Status {resp.status})")

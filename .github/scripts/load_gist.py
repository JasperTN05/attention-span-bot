"""Lädt data.json aus einem GitHub Gist."""
import os
import json
import urllib.request

GIST_ID = os.environ.get("GIST_ID", "")
GIST_TOKEN = os.environ.get("GIST_TOKEN", "")

if not GIST_ID or not GIST_TOKEN:
    print("Keine Gist-Credentials – starte mit leerem Datensatz")
    with open("data.json", "w") as f:
        json.dump({"users": {}}, f)
else:
    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        headers={
            "Authorization": f"token {GIST_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    with urllib.request.urlopen(req) as resp:
        gist = json.loads(resp.read())

    files = gist.get("files", {})
    if "data.json" in files:
        content = files["data.json"]["content"]
        with open("data.json", "w", encoding="utf-8") as f:
            f.write(content)
        print("✅ data.json aus Gist geladen")
    else:
        print("⚠️ Keine data.json im Gist – starte mit leerem Datensatz")
        with open("data.json", "w") as f:
            json.dump({"users": {}}, f)

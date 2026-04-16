"""
Storage – JSON-basiert, kompatibel mit GitHub Gist als Backend.
Kann lokal (data.json) oder via Gist-API genutzt werden.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

SR_INTERVALS = [1, 3, 7, 14, 30]

DATA_FILE = os.environ.get("DATA_FILE", "data.json")


class Storage:
    def __init__(self):
        self._data = self._load()

    def _load(self):
        # Gist-Modus: GIST_DATA env var (JSON-String)
        gist_data = os.environ.get("GIST_DATA")
        if gist_data:
            try:
                return json.loads(gist_data)
            except Exception:
                pass

        # Lokale Datei
        if Path(DATA_FILE).exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"users": {}}

    def _save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _user(self, user_id: int) -> dict:
        uid = str(user_id)
        if uid not in self._data["users"]:
            self._data["users"][uid] = {
                "sessions": [],
                "entries": {},
                "active_session": None,
                "pending_recall": None,
                "chat_id": None
            }
        return self._data["users"][uid]

    # ── Active Session ──────────────────────────────────
    def set_active_session(self, user_id: int, session: dict):
        u = self._user(user_id)
        u["active_session"] = session
        u["chat_id"] = session.get("chat_id")
        self._save()

    def get_active_session(self, user_id: int) -> dict | None:
        return self._user(user_id).get("active_session")

    def clear_active_session(self, user_id: int):
        u = self._user(user_id)
        if u.get("active_session"):
            # Session in Historie
            session = u["active_session"]
            u.setdefault("sessions", []).append({
                "mode": session.get("mode"),
                "minutes": session.get("minutes"),
                "date": datetime.now(timezone.utc).isoformat()
            })
        u["active_session"] = None
        self._save()

    # ── Pending Recall ──────────────────────────────────
    def set_pending_recall(self, user_id: int, data: dict):
        self._user(user_id)["pending_recall"] = data
        self._save()

    def get_pending_recall(self, user_id: int) -> dict | None:
        return self._user(user_id).get("pending_recall")

    def clear_pending_recall(self, user_id: int):
        self._user(user_id)["pending_recall"] = None
        self._save()

    # ── Learning Entries ────────────────────────────────
    def add_learning_entry(self, user_id: int, entry: dict) -> str:
        entry_id = str(uuid.uuid4())[:8]
        self._user(user_id)["entries"][entry_id] = entry
        self._save()
        return entry_id

    def get_due_reviews(self, user_id: int) -> list[tuple[str, dict]]:
        now = datetime.now(timezone.utc)
        entries = self._user(user_id).get("entries", {})
        due = []
        for eid, entry in entries.items():
            next_review_str = entry.get("next_review")
            if not next_review_str:
                continue
            next_review = datetime.fromisoformat(next_review_str)
            if now >= next_review:
                due.append((eid, entry))
        due.sort(key=lambda x: x[1].get("next_review", ""))
        return due

    def complete_review(self, user_id: int, entry_id: str, recall_text: str):
        entries = self._user(user_id).get("entries", {})
        if entry_id not in entries:
            return
        entry = entries[entry_id]
        count = entry.get("review_count", 0) + 1
        entry["review_count"] = count
        entry.setdefault("reviews", []).append({
            "text": recall_text,
            "date": datetime.now(timezone.utc).isoformat()
        })

        # Nächstes Intervall
        if count < len(SR_INTERVALS):
            from datetime import timedelta
            days = SR_INTERVALS[count]
            entry["next_review"] = (
                datetime.now(timezone.utc) + timedelta(days=days)
            ).isoformat()
        else:
            entry["next_review"] = None  # Vollständig gelernt

        self._save()

    # ── Stats ───────────────────────────────────────────
    def get_stats(self, user_id: int) -> dict:
        u = self._user(user_id)
        sessions = u.get("sessions", [])
        entries = u.get("entries", {})
        due = self.get_due_reviews(user_id)

        lesen = sum(1 for s in sessions if s.get("mode") == "lesen")
        lernen = sum(1 for s in sessions if s.get("mode") == "lernen")
        total_min = sum(s.get("minutes", 0) for s in sessions)
        completed = sum(
            e.get("review_count", 0) for e in entries.values()
        )

        return {
            "lesen_sessions": lesen,
            "lernen_sessions": lernen,
            "total_minutes": total_min,
            "total_entries": len(entries),
            "completed_reviews": completed,
            "due_reviews": len(due)
        }

    # ── Alle User (für scheduled reminders) ────────────
    def get_all_users(self) -> list[int]:
        return [int(uid) for uid in self._data["users"].keys()]

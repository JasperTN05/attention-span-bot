"""
Standalone-Script für GitHub Actions Cron-Job.
Prüft fällige Wiederholungen und benachrichtigt User per Telegram.
"""
import asyncio
import os
from datetime import datetime, timezone

import httpx

from storage import Storage

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


async def send_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })


async def main():
    storage = Storage()
    all_users = storage.get_all_users()
    now = datetime.now(timezone.utc)
    sent = 0

    for user_id in all_users:
        due = storage.get_due_reviews(user_id)
        if not due:
            continue

        # Chat-ID aus letzter Session
        user_data = storage._user(user_id)
        chat_id = user_data.get("chat_id")
        if not chat_id:
            continue

        topics = [e["topic"] for _, e in due[:3]]
        topics_text = "\n".join(f"• _{t}_" for t in topics)
        extra = f"\n_...und {len(due)-3} weitere_" if len(due) > 3 else ""

        text = (
            f"🔁 *Wiederholungs-Erinnerung*\n\n"
            f"Du hast *{len(due)} Thema(s)* zum Wiederholen:\n"
            f"{topics_text}{extra}\n\n"
            f"Starte mit /wiederholungen 💪"
        )

        await send_message(chat_id, text)
        sent += 1
        print(f"Erinnerung an user {user_id}: {len(due)} fällig")

    print(f"✅ {sent} Erinnerung(en) gesendet")


if __name__ == "__main__":
    asyncio.run(main())

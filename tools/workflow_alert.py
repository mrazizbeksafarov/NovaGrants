"""Dependency-free alert when installation/tests prevent the bot from starting."""

import json
import http.client
import os
import re


def send_startup_alert():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    admin = os.getenv("ADMIN_ID", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "")
    run = os.getenv("GITHUB_RUN_ID", "")
    if not token or not admin:
        print("Startup alert is not configured.")
        return False
    text = "Nova Grants: tayyorlash yoki tekshirish bosqichi tugamadi; bot ishga tushmadi."
    if re.fullmatch(r"[\w.-]+/[\w.-]+", repo) and run.isdigit():
        text += f"\nhttps://github.com/{repo}/actions/runs/{run}"
    connection = http.client.HTTPSConnection("api.telegram.org", timeout=20)
    try:
        connection.request("POST", f"/bot{token}/sendMessage",
                           body=json.dumps({"chat_id": admin, "text": text}).encode(),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        ok = response.status == 200 and json.loads(response.read()).get("ok") is True
        print("Startup alert delivered." if ok else "Startup alert rejected.")
        return ok
    except Exception as exc:
        # HTTP errors can contain the request path, which contains a bot token.
        print(f"Startup alert was not confirmed ({type(exc).__name__}).")
        return False
    finally:
        connection.close()


if __name__ == "__main__":
    send_startup_alert()

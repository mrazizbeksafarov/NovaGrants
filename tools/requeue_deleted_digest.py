"""Explicit operator repair for a user-confirmed deleted digest; never automatic."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from delivery_journal import release_confirmed_deleted_digest
from telegram_bot import CHANNEL_ID


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--message-id", type=int, required=True)
    parser.add_argument("--confirmed-deleted", action="store_true", required=True)
    args = parser.parse_args()
    database.init_db(strict=True)
    release_confirmed_deleted_digest(CHANNEL_ID, args.message_id)
    print("Confirmed deleted digest archived; only its records requeued. No Telegram sends.")

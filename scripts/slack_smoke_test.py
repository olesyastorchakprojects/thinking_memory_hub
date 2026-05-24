from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Any

import httpx


def build_payload(*, bot_user_id: str, channel: str, text: str) -> dict[str, Any]:
    now = time.time()
    ts = f"{now:.6f}"
    return {
        "type": "event_callback",
        "team_id": "TLOCALTEST",
        "api_app_id": "ALOCALTEST",
        "event": {
            "type": "app_mention",
            "user": "ULOCALTEST",
            "text": f"<@{bot_user_id}> {text}",
            "channel": channel,
            "ts": ts,
            "event_ts": ts,
        },
        "event_id": f"Ev{int(now * 1000)}",
        "event_time": int(now),
        "authorizations": [
            {
                "enterprise_id": None,
                "team_id": "TLOCALTEST",
                "user_id": "ULOCALTEST",
                "is_bot": True,
                "is_enterprise_install": False,
            }
        ],
        "is_ext_shared_channel": False,
        "context_team_id": "TLOCALTEST",
        "context_enterprise_id": None,
    }


def sign_request(*, signing_secret: str, body: bytes, timestamp: str) -> str:
    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backend-base-url",
        default="http://127.0.0.1:8081",
        help="Backend base URL, default: http://127.0.0.1:8081",
    )
    parser.add_argument("--channel", required=True, help="Slack channel ID to place in the fake event")
    parser.add_argument("--bot-user-id", required=True, help="Slack bot user ID to mention in the fake event")
    parser.add_argument("--text", required=True, help="User text after the bot mention")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
    if not signing_secret:
        print("SLACK_SIGNING_SECRET is not set", file=sys.stderr)
        return 1

    payload = build_payload(
        bot_user_id=args.bot_user_id,
        channel=args.channel,
        text=args.text,
    )
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = sign_request(
        signing_secret=signing_secret,
        body=body,
        timestamp=timestamp,
    )

    response = httpx.post(
        f"{args.backend_base_url.rstrip('/')}/slack/events",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
        timeout=20,
    )
    print(f"HTTP {response.status_code}")
    print(response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())

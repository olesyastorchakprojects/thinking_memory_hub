# Slack Setup

## Goal

Connect a real Slack app to the backend through the Events API and verify the
local `/slack/events` endpoint with a signed smoke test.

## Required Backend Env Vars

Set these in `.env` before starting the backend:

```env
SLACK_SIGNING_SECRET=...
SLACK_BOT_TOKEN=xoxb-...
SLACK_API_BASE_URL=https://slack.com/api
```

`SLACK_API_BASE_URL` is optional and defaults to `https://slack.com/api`.

## Slack App Setup

1. Create a new app at [api.slack.com/apps](https://api.slack.com/apps).
2. Open `Basic Info` and copy the app `Signing Secret`.
3. Open `OAuth & Permissions`.
4. Add bot token scopes:
   - `app_mentions:read`
   - `chat:write`
5. Install the app to your workspace and copy the bot token.
6. Open `Event Subscriptions`.
7. Enable events.
8. Set the Request URL to your public backend URL plus:

```text
/slack/events
```

Example:

```text
https://your-public-url.example/slack/events
```

9. Subscribe to the bot event:
   - `app_mention`
10. Save changes.

Slack will send a `url_verification` request during setup. The backend already
handles that flow.

## Local Backend Run

Start the backend with your normal environment loaded:

```bash
set -a
source .env
set +a
PYTHONPATH=app ./.venv/bin/python -m backend.main
```

By default the backend listens on:

```text
http://127.0.0.1:8081
```

## Public Tunnel

Slack needs a public HTTPS URL for real Events API delivery.

Any HTTPS tunnel is fine. For example:

```bash
cloudflared tunnel --url http://127.0.0.1:8081
```

Take the public HTTPS URL from the tunnel and set:

```text
https://.../slack/events
```

as the Slack Request URL.

## Local Smoke Test

You can send a signed fake Slack `app_mention` event into your local backend:

```bash
set -a
source .env
set +a
PYTHONPATH=app ./.venv/bin/python scripts/slack_smoke_test.py \
  --backend-base-url http://127.0.0.1:8081 \
  --channel C12345678 \
  --bot-user-id U12345678 \
  --text "чем отличаются prompts и resources"
```

What this does:

- builds a Slack-style `event_callback`
- signs it with `SLACK_SIGNING_SECRET`
- POSTs it to `/slack/events`

If `SLACK_BOT_TOKEN` is valid and the channel exists, the backend will then try
to reply through `chat.postMessage`.

## Recommended Real-World Smoke Test

1. Start the backend locally.
2. Expose it through an HTTPS tunnel.
3. Configure Slack Request URL.
4. Invite the app to a test channel.
5. Mention the bot in Slack:

```text
@your-bot чем отличаются prompts и resources
```

Expected result:

- Slack delivers an `app_mention` event.
- Backend verifies the Slack signature.
- Backend routes the message through `MessageService`.
- Backend posts a reply into the same thread or message context.

## Notes

- Current `v1` handles `app_mention`.
- Direct messages are not wired yet.
- `note_id` is not part of Slack-facing UX.

## References

- Slack Events API: https://docs.slack.dev/apis/events-api/
- Verifying requests from Slack: https://docs.slack.dev/authentication/verifying-requests-from-slack/
- `chat:write` scope: https://docs.slack.dev/reference/scopes/chat.write/

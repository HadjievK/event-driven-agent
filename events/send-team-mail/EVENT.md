---
name: send-team-mail
description: >
  Sends a short status-update email to the dev team.
  Fires every 3 minutes on a schedule.
type: scheduled
schedule: every 3 minutes
active: false
action:
  mcp: mail_send
  params:
    to: references/team-members.md
    subject: "The AEP is coming!"
    body: references/mail-template.md
---

# send-team-mail

Every 10 minutes this event fires and calls the `mail_send` MCP tool
with the recipients from `references/team-members.md` and the body
from `references/mail-template.md`.

## How to change things

| What | Where |
|---|---|
| Who gets the mail | `references/team-members.md` |
| What the mail says | `references/mail-template.md` |
| How often it fires | `schedule:` line above |
| How the mail is actually sent | `action.mcp` above |

---
name: hello-desi-email
description: >
  Send email to Desi every 2 minutes
type: scheduled
schedule: every 2 minutes
active: false
action:
  mcp: mail_send
  params:
    to: references/team-members.md
    subject: "Hello Desi"
    body: references/mail-template.md
---

# hello-desi-email

Send email to Desi every 2 minutes

Fires on schedule: `every 2 minutes`
Sends to recipients in `references/team-members.md`
Uses template from `references/mail-template.md`

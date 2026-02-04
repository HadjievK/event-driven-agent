---
name: sent-mail-joro
description: >
  Send mail to Joro every 2 minutes
type: scheduled
schedule: every 2 minutes
action:
  mcp: mail_send
  params:
    to: references/team-members.md
    subject: "Aideee nshate"
    body: references/mail-template.md
---

# sent-mail-joro

Send mail to Joro every 2 minutes

Fires on schedule: `every 2 minutes`
Sends to recipients in `references/team-members.md`
Uses template from `references/mail-template.md`

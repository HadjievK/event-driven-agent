---
name: weekly-report-email
description: >
  Send weekly report email every Monday at 10:00 AM
type: scheduled
schedule: every Monday at 10:00 AM
action:
  mcp: mail_send
  params:
    to: references/team-members.md
    subject: "Weekly Report"
    body: references/mail-template.md
---

# weekly-report-email

Send weekly report email every Monday at 10:00 AM

Fires on schedule: `every Monday at 10:00 AM`
Sends to recipients in `references/team-members.md`
Uses template from `references/mail-template.md`

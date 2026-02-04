---
name: test-sap-email
description: >
  Send test email to krisihadjiev@gmail.com every 2 minutes
type: scheduled
schedule: every 2 minutes
action:
  mcp: mail_send
  params:
    to: references/team-members.md
    subject: "test sap"
    body: references/mail-template.md
---

# test-sap-email

Send test email to krisihadjiev@gmail.com every 2 minutes

Fires on schedule: `every 2 minutes`
Sends to recipients in `references/team-members.md`
Uses template from `references/mail-template.md`

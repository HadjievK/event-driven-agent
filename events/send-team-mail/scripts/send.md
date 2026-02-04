# Send Team Status Mail

This script runs every time the `send-team-mail` event fires.

## Implementation

Uses **nodemailer** to send emails from Gmail to Outlook recipients.

## Steps

1. Read the recipient list from `references/team-members.md`.
   Each line that is not blank and does not start with `#` is one email address.

2. Read the mail body from `references/mail-template.md`.

3. Send email using Gmail SMTP via nodemailer with:
   - **from**    → Gmail account (configured in .env)
   - **to**      → the list of addresses from step 1
   - **subject** → `Dev Team — Status Update`
   - **body**    → the content from step 2

4. Log the result (success / failure + timestamp).

## Configuration

Set these environment variables in `.env`:

```
GMAIL_USER=your-gmail@gmail.com
GMAIL_APP_PASSWORD=your-app-password-here
```

Get Gmail app password from: https://myaccount.google.com/apppasswords

## Output Format

```json
{
  "status": "sent",
  "message_id": "<unique-id>",
  "timestamp": "2026-02-03T10:00:00.000Z",
  "recipients": 3
}
```
```

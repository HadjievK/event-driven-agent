"""
gmail_mail.py  —  Send email via Gmail SMTP
─────────────────────────────────────────────────────
Simple Gmail integration using SMTP with App Password.

SETUP:
1. Enable 2-Step Verification in your Google Account:
   https://myaccount.google.com/security

2. Generate App Password:
   https://myaccount.google.com/apppasswords
   → Select "Mail" and your device
   → Copy the 16-character password

3. Add to .env:
   GMAIL_USER=your.email@gmail.com
   GMAIL_APP_PASSWORD=your-16-char-app-password

That's it! No OAuth, no device code flow.
"""

from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

# ─── config ──────────────────────────────────────────────────────────────────
GMAIL_USER     = os.environ.get("GMAIL_USER", "").strip()
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

async def send_mail(to: list[str], subject: str, body: str) -> dict[str, Any]:
    """Send email via Gmail SMTP."""
    
    if not GMAIL_USER or not GMAIL_PASSWORD:
        return {
            "status": "error",
            "error": "GMAIL_USER or GMAIL_APP_PASSWORD not set in .env"
        }
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = ", ".join(to)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect and send
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        
        print(f"  ✅ Email sent to {', '.join(to)}")
        return {
            "status": "sent",
            "message_id": f"gmail-{subject[:20]}"
        }
    
    except smtplib.SMTPAuthenticationError:
        return {
            "status": "error",
            "error": "Gmail authentication failed. Check GMAIL_USER and GMAIL_APP_PASSWORD in .env"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to send email: {str(e)}"
        }

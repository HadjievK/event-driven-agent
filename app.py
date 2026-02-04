"""
app.py — AEP Claude Agent with Flask
─────────────────────────────────────
A simple AI agent that manages AEP events using Flask instead of Gradio.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

# ─── env ─────────────────────────────────────────────────────────────────────
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "").strip()

if not OPENAI_API_KEY:
    print("⚠️  OPENAI_API_KEY not set.  Add it to your .env file.")

client = OpenAI(api_key=OPENAI_API_KEY)

# ─── paths ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
EVENTS_DIR  = BASE_DIR / "events"

# ─── import our event engine ─────────────────────────────────────────────────
import event_engine as ee
import gmail_mail  # Gmail SMTP integration

# ══════════════════════════════════════════════════════════════════════════════
# SHARED STATE
# ══════════════════════════════════════════════════════════════════════════════

event_log: list[dict] = []
engine: ee.AEPEventEngine | None = None
engine_loop: asyncio.AbstractEventLoop | None = None

# ══════════════════════════════════════════════════════════════════════════════
# GMAIL SMTP EMAIL SENDER
# ══════════════════════════════════════════════════════════════════════════════

# ── REAL sender (used when GMAIL_USER is set) ────────────────────────────
async def _real_mail_send(to: list[str], subject: str, body: str, event_name: str = "unknown-event") -> dict:
    """Calls Gmail SMTP via gmail_mail module."""
    result = await gmail_mail.send_mail(to=to, subject=subject, body=body)
    status_label = "✅ sent" if result["status"] == "sent" else f"❌ {result.get('error','?')}"
    event_log.append({
        "time":    datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC"),
        "event":   event_name,
        "action":  "mail_send (Gmail)",
        "status":  status_label,
        "detail":  f"→ {len(to)} recipient(s)  |  {result.get('message_id', 'n/a')}",
        "to":      ", ".join(to),
        "subject": subject,
    })
    return result


# ── MOCK sender (demo mode) ───────────────────────────────────────────────
async def _mock_mail_send(to: list[str], subject: str, body: str, event_name: str = "unknown-event") -> dict:
    """Simulates email sending for demo purposes."""
    await asyncio.sleep(0.3)
    msg_id = f"mock-{len(event_log) + 1:04d}"
    event_log.append({
        "time":    datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC"),
        "event":   event_name,
        "action":  "mail_send (MOCK)",
        "status":  "✅ sent (mock)",
        "detail":  f"→ {len(to)} recipient(s)  |  {msg_id}",
        "to":      ", ".join(to),
        "subject": subject,
    })
    return {"status": "sent", "message_id": msg_id}


# ── ROUTER: picks real or mock based on .env ───────────────────────────────
_USE_GMAIL = bool(GMAIL_USER)

if _USE_GMAIL:
    print(f"✅ Gmail enabled for {GMAIL_USER}")
else:
    print("⚠️  GMAIL_USER not set — running in MOCK mode.")
    print("   Set GMAIL_USER and GMAIL_APP_PASSWORD in .env to enable real email sending.")


async def mock_mail_send(params: dict) -> dict:
    """Main mail sender — routes to real or mock based on configuration."""
    raw_to  = params.get("to", [])
    subject = params.get("subject", "(no subject)")
    body    = params.get("body", "")
    event_name = params.get("_event_name", "unknown-event")

    # Parse recipients
    if isinstance(raw_to, str):
        to = [line.strip() for line in raw_to.splitlines()
              if line.strip() and not line.strip().startswith("#")]
    else:
        to = raw_to

    if not to:
        msg_id = f"error-{len(event_log) + 1:04d}"
        status = "❌ error: No recipients"
        event_log.append({
            "time":    datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC"),
            "event":   event_name,
            "action":  "mail_send",
            "status":  status,
            "detail":  "No valid recipients found",
            "to":      "",
            "subject": subject,
        })
        return {"status": "error", "message_id": msg_id}

    # Route to real or mock
    if _USE_GMAIL:
        return await _real_mail_send(to, subject, body, event_name)
    else:
        return await _mock_mail_send(to, subject, body, event_name)


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE BOOT
# ══════════════════════════════════════════════════════════════════════════════

def _boot_engine():
    """Create the engine, load events, start the scheduler in a daemon thread."""
    global engine, engine_loop

    mcp = ee.MCPClient()
    mcp.register_tool("mail_send", mock_mail_send)

    engine = ee.AEPEventEngine(events_root=EVENTS_DIR, mcp=mcp)
    engine.load()

    def _run():
        global engine_loop
        try:
            engine_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(engine_loop)
            engine_loop.run_until_complete(engine.run())
        except Exception as e:
            print(f"❌ Event engine crashed: {e}")
            import traceback
            traceback.print_exc()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print("⏳ Event engine started in background thread.")

_boot_engine()

# ══════════════════════════════════════════════════════════════════════════════
# CLAUDE AGENT
# ══════════════════════════════════════════════════════════════════════════════

def _event_state_snapshot() -> str:
    """Build a text block describing current events."""
    if not engine:
        return "No events loaded."
    lines = []
    for ev in engine.events:
        status_icon = "🟢 ACTIVE" if ev.active else "🔴 INACTIVE"
        last   = engine._last_fired.get(ev.name)
        if last:
            status = f"{status_icon}, last fired {last.strftime('%H:%M:%S UTC')}"
        else:
            status = f"{status_icon}, never fired"
        lines.append(
            f"  • {ev.name}\n"
            f"      description: {ev.description.strip()}\n"
            f"      type:        {ev.event_type}\n"
            f"      schedule:    {ev.schedule_raw}\n"
            f"      action:      {ev.action.get('mcp') or ev.action.get('script')}\n"
            f"      status:      {status}"
        )
    return "\n".join(lines) if lines else "No events loaded."

def _recent_log(n: int = 5) -> str:
    """Last N log entries as text for the prompt."""
    if not event_log:
        return "  (no events have fired yet)"
    lines = []
    for entry in event_log[-n:]:
        lines.append(f"  [{entry['time']}] {entry['event']} → {entry['status']}  {entry['detail']}")
    return "\n".join(lines)

SYSTEM_PROMPT_TEMPLATE = """\
You are the AEP Event Agent — a smart assistant with an "event-creator" skill for managing event-driven workflows.

══ CURRENT EVENTS ══
{event_state}

══ RECENT EVENT LOG ══
{recent_log}

══ SKILL: EVENT-CREATOR ══

Guide for creating effective events. Use this skill when users want to create a new scheduled event.

**When to use:** User requests like:
- "Send mail every 2 minutes to xyz@mail.com with subject X and body Y"
- "Create an event that emails the team every hour"
- "Set up automatic status updates every 5 minutes"

**How it works:**
1. Parse the user's request to extract:
   - Schedule: "every 2 minutes", "every hour", "every day at 9 AM"
   - Recipients: email addresses (can be inline or reference a file)
   - Subject: email subject line
   - Body: email body/template (can be inline or reference a file)

2. Create a kebab-case event name from the description (e.g., "status-update", "team-notification")

3. Generate the <aep_action> block with:
   - name: kebab-case event name
   - description: brief description
   - schedule: natural language schedule
   - recipients: email addresses (one per line)
   - subject: email subject
   - body: email body template

**Example user request:**
"Send mail every 2 minutes to receiver@mail.com with subject 'Test' and body 'Hello, this is AEP!'"

**Your response should include:**
"I'll create an event that sends email every 2 minutes to receiver@mail.com."

<aep_action>
{{"action": "create", "name": "test-email", "description": "Send test email every 2 minutes", "schedule": "every 2 minutes", "recipients": "receiver@mail.com", "subject": "Test", "body": "Hello, this is AEP!"}}
</aep_action>

══ WHAT YOU CAN DO ══

1. **Answer questions** about events, schedules, and the event log.

2. **Activate an event** to start firing it on schedule:
   
   When user says:
   - "send mail to desi" → activate "hello-desi-email" event
   - "send team mail" → activate "send-team-mail" event
   - "activate <event-name>" → activate that specific event
   
   Match the user's request to the most relevant INACTIVE event and activate it:

     <aep_action>
     {{"action": "activate", "name": "<exact-event-name>"}}
     </aep_action>

   Note: Events are INACTIVE by default. They only start firing when activated.

3. **Fire an event once** immediately (without activating it):

     <aep_action>
     {{"action": "fire", "name": "<exact-event-name>"}}
     </aep_action>

4. **Deactivate an event** to stop it from firing:
   
   When user says "stop sending mail to desi", "deactivate event":

     <aep_action>
     {{"action": "deactivate", "name": "<exact-event-name>"}}
     </aep_action>

5. **Create a new event** using the event-creator skill above.
   explanation AND include:

     <aep_action>
     {{"action": "create", "name": "<kebab-case-name>", "description": "<one line>", "schedule": "<natural language>", "mcp_tool": "<tool name>"}}
     </aep_action>

6. **Delete an event** permanently when user says "delete event", "remove event":

     <aep_action>
     {{"action": "delete", "name": "<exact-event-name>"}}
     </aep_action>

7. List events — just describe what's loaded.  No special tag needed.

══ RULES ══
• Keep responses concise and friendly.
• When user requests to send/start emails, ACTIVATE the event (not just fire once).
• If user asks to "send mail to desi", activate hello-desi-email so it keeps firing.
• If user asks to "stop sending", DEACTIVATE the event (don't delete it).
• If the user asks to create, fire, activate, deactivate, or delete something, always include the <aep_action> block.
• The mail MCP tool is called "mail_send".

══ RULES ══
• Keep responses concise and friendly.
• If the user asks to create, fire, or delete something, always include the <aep_action> block.
• The mail MCP tool is called "mail_send".
"""

def build_system_prompt() -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        event_state = _event_state_snapshot(),
        recent_log  = _recent_log(),
    )

def parse_aep_action(text: str) -> dict | None:
    """Extract <aep_action>...</aep_action> JSON from Claude's response."""
    m = re.search(r"<aep_action>\s*(.*?)\s*</aep_action>", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

async def _fire_event_async(event_name: str) -> str:
    """Fire a single event right now."""
    if not engine:
        return "❌ Engine not running."
    for ev in engine.events:
        if ev.name == event_name:
            await engine._dispatch(ev)
            engine._last_fired[ev.name] = datetime.now(tz=timezone.utc)
            return f"✅ Fired **{event_name}** manually."
    return f"❌ Event '{event_name}' not found."

def fire_event_now(event_name: str) -> str:
    """Thread-safe bridge: schedule the async fire on the engine's loop."""
    if engine_loop and engine_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(_fire_event_async(event_name), engine_loop)
        return future.result(timeout=10)
    return "❌ Engine loop not running."

def create_event_on_disk(cmd: dict) -> str:
    """Create a new event folder from the <aep_action> create command."""
    name        = cmd.get("name", "").strip().lower().replace(" ", "-")
    description = cmd.get("description", "No description.")
    schedule    = cmd.get("schedule", "every 10 minutes")
    mcp_tool    = cmd.get("mcp_tool", "mail_send")
    
    # NEW: Support inline recipients, subject, and body
    recipients  = cmd.get("recipients", "")
    subject     = cmd.get("subject", "Event Notification")
    body        = cmd.get("body", "This is an automated event notification.")

    if not name:
        return "❌ No event name provided."

    try:
        ee.NLSchedule.parse(schedule)
    except ValueError as e:
        return f"❌ Bad schedule: {e}"

    event_dir = EVENTS_DIR / name
    if event_dir.exists():
        return f"⚠️  Event '{name}' already exists."

    event_dir.mkdir(parents=True)
    (event_dir / "scripts").mkdir()
    (event_dir / "references").mkdir()

    # Create team-members.md with recipients
    team_members_content = "# Team members — one email per line\n# Lines starting with # are ignored\n\n"
    if recipients:
        # Split by comma, newline, or semicolon
        recipient_list = [r.strip() for r in recipients.replace(',', '\n').replace(';', '\n').split('\n') if r.strip()]
        team_members_content += "\n".join(recipient_list) + "\n"
    else:
        team_members_content += "recipient@example.com\n"
    
    (event_dir / "references" / "team-members.md").write_text(team_members_content, encoding="utf-8")
    
    # Create mail-template.md with body
    (event_dir / "references" / "mail-template.md").write_text(body, encoding="utf-8")

    # Create EVENT.md
    event_md = (
        f"---\n"
        f"name: {name}\n"
        f"description: >\n"
        f"  {description}\n"
        f"type: scheduled\n"
        f"schedule: {schedule}\n"
        f"action:\n"
        f"  mcp: {mcp_tool}\n"
        f"  params:\n"
        f"    to: references/team-members.md\n"
        f"    subject: \"{subject}\"\n"
        f"    body: references/mail-template.md\n"
        f"---\n\n"
        f"# {name}\n\n"
        f"{description}\n\n"
        f"Fires on schedule: `{schedule}`\n"
        f"Sends to recipients in `references/team-members.md`\n"
        f"Uses template from `references/mail-template.md`\n"
    )
    (event_dir / "EVENT.md").write_text(event_md, encoding="utf-8")

    if engine:
        try:
            ev = ee.parse_event_md(event_dir)
            engine.events.append(ev)
            event_log.append({
                "time":    datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC"),
                "event":   name,
                "action":  "created",
                "status":  "✅ created",
                "detail":  f"schedule: {schedule}  |  tool: {mcp_tool}",
                "to":      "",
                "subject": "",
            })
            return f"✅ Created event **{name}** — fires {schedule}."
        except Exception as e:
            return f"⚠️  Folder created but engine reload failed: {e}"

    return f"✅ Created event folder **{name}** on disk."

def delete_event(event_name: str) -> str:
    """Delete an event from disk and remove it from the running engine."""
    if not event_name:
        return "❌ No event name provided."
    
    event_dir = EVENTS_DIR / event_name
    if not event_dir.exists():
        return f"❌ Event '{event_name}' not found."
    
    try:
        # Remove from engine first
        if engine:
            engine.events = [ev for ev in engine.events if ev.name != event_name]
            if event_name in engine._last_fired:
                del engine._last_fired[event_name]
        
        # Delete the folder
        import shutil
        shutil.rmtree(event_dir)
        
        event_log.append({
            "time":    datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC"),
            "event":   event_name,
            "action":  "deleted",
            "status":  "✅ deleted",
            "detail":  "Event removed",
            "to":      "",
            "subject": "",
        })
        
        return f"✅ Deleted event **{event_name}** — it will no longer fire."
    except Exception as e:
        return f"❌ Error deleting event: {e}"

def activate_event(event_name: str) -> str:
    """Activate an event so it starts firing on schedule."""
    if not event_name:
        return "❌ No event name provided."
    
    if not engine:
        return "❌ Engine not running."
    
    for ev in engine.events:
        if ev.name == event_name:
            ev.active = True
            event_log.append({
                "time":    datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC"),
                "event":   event_name,
                "action":  "activated",
                "status":  "🟢 activated",
                "detail":  f"Will fire on schedule: {ev.schedule_raw}",
                "to":      "",
                "subject": "",
            })
            return f"🟢 Activated event **{event_name}** — it will now fire {ev.schedule_raw}."
    
    return f"❌ Event '{event_name}' not found."

def deactivate_event(event_name: str) -> str:
    """Deactivate an event so it stops firing on schedule."""
    if not event_name:
        return "❌ No event name provided."
    
    if not engine:
        return "❌ Engine not running."
    
    for ev in engine.events:
        if ev.name == event_name:
            ev.active = False
            event_log.append({
                "time":    datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC"),
                "event":   event_name,
                "action":  "deactivated",
                "status":  "🔴 deactivated",
                "detail":  "Event stopped",
                "to":      "",
                "subject": "",
            })
            return f"🔴 Deactivated event **{event_name}** — it will no longer fire automatically."
    
    return f"❌ Event '{event_name}' not found."

def execute_action(cmd: dict) -> str:
    """Route an <aep_action> command."""
    action = cmd.get("action", "")

    if action == "fire":
        # Support both "name" and "event" for backward compatibility
        event_name = cmd.get("name") or cmd.get("event", "")
        return fire_event_now(event_name)
    elif action == "create":
        return create_event_on_disk(cmd)
    elif action == "delete":
        event_name = cmd.get("name") or cmd.get("event", "")
        return delete_event(event_name)
    elif action == "activate":
        event_name = cmd.get("name") or cmd.get("event", "")
        return activate_event(event_name)
    elif action == "deactivate":
        event_name = cmd.get("name") or cmd.get("event", "")
        return deactivate_event(event_name)

    return f"⚠️  Unknown action: {action}"

# ══════════════════════════════════════════════════════════════════════════════
# FLASK APP
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/events')
def get_events():
    """Get current events."""
    if not engine:
        return jsonify([])
    
    events = []
    for ev in engine.events:
        last = engine._last_fired.get(ev.name)
        events.append({
            "name": ev.name,
            "type": ev.event_type,
            "schedule": ev.schedule_raw or "—",
            "action": ev.action.get("mcp") or ev.action.get("script") or "—",
            "last_fired": last.strftime("%H:%M:%S UTC") if last else "not yet",
        })
    return jsonify(events)

@app.route('/api/log')
def get_log():
    """Get event log."""
    return jsonify(event_log)

@app.route('/api/fire', methods=['POST'])
def fire():
    """Fire an event manually."""
    data = request.json
    event_name = data.get('event', '').strip()
    if not event_name:
        return jsonify({"error": "No event name provided"}), 400
    
    result = fire_event_now(event_name)
    return jsonify({"result": result})

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat with Claude."""
    data = request.json
    user_msg = data.get('message', '').strip()
    history = data.get('history', [])
    
    if not user_msg:
        return jsonify({"error": "No message provided"}), 400
    
    if not OPENAI_API_KEY:
        return jsonify({"reply": "⚠️  OPENAI_API_KEY not set.  Add it to your .env file."})
    
    # Build messages list
    messages = []
    for h in history:
        if h.get('user'):
            messages.append({"role": "user", "content": h['user']})
        if h.get('assistant'):
            messages.append({"role": "assistant", "content": h['assistant']})
    messages.append({"role": "user", "content": user_msg})
    
    try:
        # Add system prompt as first message
        messages_with_system = [
            {"role": "system", "content": build_system_prompt()}
        ] + messages
        
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            messages=messages_with_system,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"❌ API error: {e}"
        return jsonify({"reply": reply})
    
    # Check for action
    cmd = parse_aep_action(reply)
    action_result = None
    if cmd:
        action_result = execute_action(cmd)
    
    return jsonify({"reply": reply, "action_result": action_result})

if __name__ == "__main__":
    print("\n🚀 Starting AEP Event Agent on http://localhost:7860")
    print("   Press Ctrl+C to stop\n")
    try:
        app.run(host="0.0.0.0", port=7860, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Error starting Flask server: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)

"""
cli.py - Simple CLI to test the AEP event system without Gradio
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import event engine
import event_engine as ee

# Import the mail sender from main
sys.path.insert(0, str(Path(__file__).parent))

BASE_DIR = Path(__file__).parent
EVENTS_DIR = BASE_DIR / "events"

async def main():
    print("="*60)
    print("AEP Event Engine - CLI Test")
    print("="*60)
    
    # Create mock MCP client
    from main import mock_mail_send
    mcp = ee.MCPClient()
    mcp.register_tool("mail_send", mock_mail_send)
    
    # Create engine and load events
    engine = ee.AEPEventEngine(events_root=EVENTS_DIR, mcp=mcp)
    engine.load()
    
    print(f"\nLoaded {len(engine.events)} event(s):\n")
    for ev in engine.events:
        print(f"  📦 {ev.name}")
        print(f"     Description: {ev.description.strip()}")
        print(f"     Schedule: {ev.schedule_raw}")
        print(f"     Type: {ev.event_type}")
        print(f"     Action: {ev.action.get('mcp') or ev.action.get('script')}")
        print()
    
    # Fire the send-team-mail event manually
    print("🚀 Firing 'send-team-mail' event manually...")
    print("-"*60)
    
    for ev in engine.events:
        if ev.name == "send-team-mail":
            await engine._dispatch(ev)
            print("\n✅ Event fired successfully!")
            break
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())

"""
send_mail.py
────────────
Python wrapper to execute the nodemailer script for sending team emails.
Called by the event engine when the send-team-mail event fires.
"""

import subprocess
import sys
import json
from pathlib import Path


def send_team_mail():
    """
    Execute the Node.js mailer script and return the result.
    """
    script_dir = Path(__file__).parent
    node_script = script_dir / "send_mail.js"
    
    if not node_script.exists():
        return {
            "status": "error",
            "error": f"send_mail.js not found at {node_script}"
        }
    
    try:
        result = subprocess.run(
            ["node", str(node_script)],
            capture_output=True,
            text=True,
            check=True,
            cwd=script_dir
        )
        
        # Parse the JSON output from the Node.js script
        output = json.loads(result.stdout)
        return output
        
    except subprocess.CalledProcessError as e:
        try:
            error_data = json.loads(e.stderr)
            return error_data
        except:
            return {
                "status": "error",
                "error": e.stderr or str(e)
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    result = send_team_mail()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") == "sent" else 1)

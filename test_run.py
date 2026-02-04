"""Test runner for main.py to catch errors"""
import sys
import traceback

try:
    print("Starting import of main.py modules...")
    import main
    print("Main imported successfully, launching...")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)

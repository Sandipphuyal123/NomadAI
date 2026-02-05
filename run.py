#!/usr/bin/env python3
import subprocess
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SERVER_DIR = BASE_DIR / "server"
REQ_FILE = BASE_DIR / "requirements.txt"

def run(cmd, cwd=None):
    print(f"\n>>> Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=False, text=True)
    if result.returncode != 0:
        sys.exit(f"Command failed: {cmd}")

if __name__ == "__main__":
    print("=== NomadAI Startup ===")
    # Install deps
    if REQ_FILE.exists():
        run(f'"{sys.executable}" -m pip install -r "{REQ_FILE}"')
    # Start server
    os.chdir(SERVER_DIR)
    run(f'"{sys.executable}" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload')

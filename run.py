#!/usr/bin/env python3
import subprocess
import sys
import os
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SERVER_DIR = BASE_DIR / "server"
REQ_FILE = BASE_DIR / "requirements.txt"

def run(cmd, cwd=None):
    print(f"\n>>> Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=False, text=True)
    if result.returncode != 0:
        sys.exit(f"Command failed: {cmd}")


def run_server(cmd, cwd=None):
    print(f"\n>>> Running: {cmd}")
    return subprocess.Popen(cmd, shell=True, cwd=cwd)

if __name__ == "__main__":
    print("=== NomadAI Startup ===")
    # Install deps
    if REQ_FILE.exists():
        run(f'"{sys.executable}" -m pip install -r "{REQ_FILE}"')
    # Start server
    local_url = "http://localhost:8000"
    os.chdir(SERVER_DIR)
    reload_flag = " --reload" if os.getenv("NOMADAI_RELOAD", "") == "1" else ""
    proc = run_server(f'"{sys.executable}" -m uvicorn main:app --host 127.0.0.1 --port 8000{reload_flag}')
    try:
        time.sleep(0.8)
        print(f"\nOpen this in your browser: {local_url}")
        try:
            webbrowser.open(local_url)
        except Exception:
            pass
        try:
            proc.wait()
        except KeyboardInterrupt:
            pass
    except KeyboardInterrupt:
        print("\nStopping server...")
        try:
            proc.terminate()
        except Exception:
            pass
    finally:
        try:
            if proc and proc.poll() is None:
                proc.terminate()
        except Exception:
            pass

#!/usr/bin/env python3
import sys
import os

# Add backend/app directory to PYTHONPATH so 'cli' acts as top-level package
backend_app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_app_path not in sys.path:
    sys.path.insert(0, backend_app_path)

from cli.main import app

if __name__ == "__main__":
    app()

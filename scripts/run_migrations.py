#!/usr/bin/env python
"""Script to run Alembic migrations with proper configuration."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set ALEMBIC_CONFIG environment variable if not set
if "ALEMBIC_CONFIG" not in os.environ:
    alembic_ini = project_root / "alembic.ini"
    if alembic_ini.exists():
        os.environ["ALEMBIC_CONFIG"] = str(alembic_ini)
        print(f"Setting ALEMBIC_CONFIG to {alembic_ini}", file=sys.stderr)
    else:
        print(f"ERROR: alembic.ini not found at {alembic_ini}", file=sys.stderr)
        print(f"Current directory: {os.getcwd()}", file=sys.stderr)
        print(f"Project root: {project_root}", file=sys.stderr)
        sys.exit(1)
else:
    print(f"Using existing ALEMBIC_CONFIG: {os.environ['ALEMBIC_CONFIG']}", file=sys.stderr)

# Change to project root directory
os.chdir(project_root)
print(f"Changed to directory: {os.getcwd()}", file=sys.stderr)

# Run alembic command
from alembic.config import main as alembic_main

if __name__ == "__main__":
    # Pass all command line arguments to alembic
    args = sys.argv[1:] if len(sys.argv) > 1 else ["upgrade", "head"]
    print(f"Running: alembic {' '.join(args)}", file=sys.stderr)
    alembic_main(argv=args)


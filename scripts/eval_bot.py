"""Bot evaluation harness CLI entrypoint (Phase 7).

Executes the full evaluation runner from backend/scripts/eval_bot.py.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

# Ensure backend directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from scripts.eval_bot import main  # type: ignore[import-not-found]

if __name__ == "__main__":
    main()

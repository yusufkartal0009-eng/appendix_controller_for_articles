"""Shared test setup."""

import os

# The preflight (scripts/preflight.py, #378) looks at the real machine and starts a container; tests must not.
os.environ.setdefault("REPRO_RADAR_SKIP_PREFLIGHT", "1")

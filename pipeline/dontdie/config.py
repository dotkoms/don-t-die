"""Runtime configuration. Everything works with defaults; no API keys required.

NCBI E-utilities work unauthenticated at 3 req/s. Supplying NCBI_API_KEY
(optional) raises the limit to 10 req/s — opt-in only.
"""
from __future__ import annotations

import os
from pathlib import Path

# pipeline/ root, regardless of where the command is run from
PACKAGE_DIR = Path(__file__).resolve().parent
PIPELINE_ROOT = PACKAGE_DIR.parent

# Landing zone for raw fetched items (gitignored).
LANDING_DIR = Path(os.environ.get("DD_LANDING_DIR", PIPELINE_ROOT / "state" / "landing"))

# Fetch log, one JSON line per run (gitignored).
FETCH_LOG = Path(os.environ.get("DD_FETCH_LOG", PIPELINE_ROOT / "state" / "fetch_log.jsonl"))

# The in-flight extraction batch, if one was submitted (gitignored). Batch
# results stay with Anthropic until collected; this file is the only local
# trace of the batch id.
EXTRACT_BATCH = Path(
    os.environ.get("DD_EXTRACT_BATCH", PIPELINE_ROOT / "state" / "extraction_batch.json")
)

# Optional NCBI API key (10 req/s instead of 3).
NCBI_API_KEY = os.environ.get("NCBI_API_KEY")

# NCBI asks for an identifying tool name; email is optional but courteous.
NCBI_TOOL = "dont-die"
NCBI_EMAIL = os.environ.get("NCBI_EMAIL")

# Unauthenticated rate limit, with headroom.
NCBI_MIN_INTERVAL = 0.4  # seconds between NCBI requests

CTGOV_BASE_URL = "https://clinicaltrials.gov/api/v2"
NCBI_EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

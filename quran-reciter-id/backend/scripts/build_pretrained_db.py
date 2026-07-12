"""
Build reciter_database.json + reciters_metadata.json from the
open-source HuggingFace model `iarhamanwaar/quran-reciter-id-ecapa`
which ships pretrained centroids for 364 famous Quran reciters.

Runs at CI build time (or manually) so the final EXE ships with a
ready-to-use fingerprint database — no model training needed.
"""
from __future__ import annotations
import json, re, sys, urllib.request
from pathlib import Path

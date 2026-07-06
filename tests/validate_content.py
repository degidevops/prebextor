#!/usr/bin/env python3
"""validate_content.py — Basic sanity-check for content-aware pipeline.

Run: python tests/validate_content.py
"""
import sys, os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import MagicMock
from prebextor.pipeline.scorer import ScoredBlock, ContentAwareScorer
from prebextor.pipeline.validator import ValidationResult

blocks = [
    ScoredBlock("div.article", 500, 5, 10, 3),
    ScoredBlock("nav.link", 30, 2, 25, 0),
    ScoredBlock("p.short", 10, 1, 0, 0),
]

scorer = ContentAwareScorer(MagicMock())
noise = scorer.get_noise_selectors(blocks)
print("Detected noise selectors:", noise)

conf = scorer.compute_confidence(blocks)
print("Overall confidence:", conf)

vr = ValidationResult("div.main", 500, 10, 0.1, 5.0, 0.9, 1)
print("Validation dict:", vr.to_dict())

print("OK")
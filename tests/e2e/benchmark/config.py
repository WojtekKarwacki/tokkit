"""Benchmark configuration - pinned repo and constants."""

REPO_URL = "https://github.com/fastapi/fastapi.git"
REPO_SHA = "0.115.6"  # tag-based pin for determinism
REPO_DIR_NAME = "fastapi"
CHARS_PER_TOKEN = 4

QUESTIONS = [
    "Dead code detection",
    "List all routes",
    "Architecture overview",
    "Search markdown documentation",
    "Compress pytest output",
    "Compress lint output",
# rev-31
]

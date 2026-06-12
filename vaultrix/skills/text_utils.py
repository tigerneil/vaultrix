"""Safe text and string manipulation utilities for Vaultrix agents.

These utilities are strictly audited and do not import dangerous modules.
"""
import re

def extract_json(text: str) -> list[str]:
    """Find all JSON-like blocks in a string."""
    pattern = r'\{[^{}]*\}'
    return re.findall(pattern, text)

def count_words(text: str) -> dict[str, int]:
    """Count word frequencies."""
    words = re.findall(r'\w+', text.lower())
    freq = {}
    for w in set(words):
        freq[w] = words.count(w)
    return freq

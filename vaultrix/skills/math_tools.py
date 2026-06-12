"""Safe mathematical and statistical utilities for Vaultrix agents.

These utilities maintain mathematical precision without requiring native subprocess bindings.
"""

def calculate_variance(data: list[float]) -> float:
    """Calculate sample variance."""
    if not data or len(data) < 2:
        return 0.0
    mean = sum(data) / len(data)
    sq_diffs = [(x - mean) ** 2 for x in data]
    return sum(sq_diffs) / (len(data) - 1)

def fibonacci(n: int) -> int:
    """Calculate nth Fibonacci number."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

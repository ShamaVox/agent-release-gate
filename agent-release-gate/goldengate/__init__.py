"""goldengate: a minimal release gate for AI agents.

Run a golden set of known-good cases against an agent, grade every output for shape, truth and
correctness, compare the run with a committed baseline, and block the release when quality drops.
Standard library only.
"""

__version__ = "1.0.0"

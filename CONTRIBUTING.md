# Contributing to Voyager

Thanks for your interest in contributing! Voyager is a research-grade
multi-agent system, and contributions of all kinds are welcome: bug reports,
documentation, tests, and features.

## Reporting bugs and requesting features

- Open a GitHub issue. For bugs, include: steps to reproduce, expected vs.
  actual behavior, your Python version and OS, and whether you ran in mock,
  capture, or replay mode.
- Check existing open issues before filing a duplicate.

## Development setup

1. Clone the repo and create a virtual environment (Python 3.11+ per README).
2. Install dependencies: `pip install -e ".[dev]"`.
3. Run the test suite:
   `pytest tests/unit -v --cov=agents --cov=graph --cov-report=xml`
   — all tests must pass before submitting a PR.
4. You can develop and test without any API keys using mock mode:
   `python3 scripts/benchmark_queries.py --inventory mock --limit 3` (smoke test;
   the full mock benchmark is `python3 scripts/benchmark_queries.py --mode compare --inventory mock`).

## Pull requests

- Keep PRs focused: one logical change per PR.
- Write clear commit messages in imperative mood.
- Add or update tests for behavior changes.
- Update documentation (README, docs/) when behavior or setup changes.
- Benchmark artifacts are versioned research data: do not modify files under
  benchmark/fixture/artifact directories in a code PR.

## Code style

- Follow the existing code style. The repo uses ruff; run `ruff check .` before
  committing.
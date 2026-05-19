# Contributing to voffice

Thank you for considering contributing! voffice is a young project and the best ideas come from real users hitting real edges.

## What's most useful right now

1. **Office packs** — define a new team in `voffice/engine.py` by adding to `ROLES`. Examples we'd love:
   - Content team (writer, SEO, designer, analyst)
   - Research team (literature, hypothesis, experimenter, reviewer)
   - Indie-game team (designer, programmer, artist, sound)
2. **Verifiers beyond pytest** — add JS/Rust/Go verification loops following the pattern in `engine.py::_run_pytest_in`.
3. **Deploy adapters** — implement `/deploy vercel`, `/deploy fly`, `/deploy gh repo create`.
4. **Bug reports** — especially around the QA loop, MsgHub timing, or file collision edge cases.

## Setup

```bash
git clone https://github.com/your-user/voffice
cd voffice
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env  # then fill in 5 keys
pytest
```

All 9 tests should pass without any API calls (they use mocks for the LLM-touching paths).

## Code style

- Python 3.10+ syntax (`x | None`, structural pattern matching OK).
- No big files. Each module in `voffice/` has one clear responsibility — see `voffice/engine.py` for the pattern.
- Type hints everywhere.
- Tests for new public API surface (mock the LLM, don't hit it).

## Pull request flow

1. Open an issue describing the change first if it's non-trivial.
2. Branch from `main`, keep commits small and descriptive (`feat:`, `fix:`, `docs:`, `test:` prefixes).
3. Ensure `pytest` passes.
4. Update README if your change is user-visible.
5. Open a PR with a screenshot or terminal recording if it's UI-affecting.

## Code of conduct

Be kind. Disagreements are about ideas, not people. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

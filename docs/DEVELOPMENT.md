# Development guide

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                                  # add ANTHROPIC_API_KEY
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add logins
pre-commit install
streamlit run app.py
```

## Tooling

This is a Python project, so JavaScript tools (ESLint, Husky) don't apply. The
equivalents:

| JS tool | Used here | Config |
|---|---|---|
| ESLint | **ruff** (`ruff check`) | `pyproject.toml` |
| Prettier | **ruff format** | `pyproject.toml` |
| Husky + lint-staged | **pre-commit** | `.pre-commit-config.yaml` |
| Jest | **pytest** | `pyproject.toml`, `tests/` |

Ruff rule sets: `E/W` (style), `F` (pyflakes), `I` (import order), `B`
(bugbear), `UP` (modern syntax), `SIM` (simplifications). Line length is 110.

```bash
ruff check .            # lint (add --fix to auto-fix)
ruff format .           # format
pytest                  # tests (no API key or network needed)
pre-commit run --all-files
```

## What runs on every commit

1. `ruff check --fix` and `ruff format`
2. Whitespace / end-of-file fixes, large-file check
3. **Block commits of anything in `sample_images/` or `output/`** (except
   `.gitkeep`), because those hold real bank data
4. `pytest`

If a hook modifies files, the commit is aborted: re-stage and commit again.
Skip hooks only in an emergency with `git commit --no-verify`.

## Tests

`tests/` mirrors `src/`. Nothing calls the Anthropic API or the network:
the pricing fetch is monkeypatched, and images are generated on the fly.

Covered: `build_record` (digit truncation, missing fields), image loading and
HEIC conversion, CSV/DataFrame output, token and cost maths.

Not covered yet: `extract_from_image` (needs a fake client) and the Streamlit
UI (`streamlit.testing.v1.AppTest` can drive it).

## Conventions

- Keep `src/` free of `print()`, `argparse`, and `st.*`; the UI lives in `app.py`.
- Treat anything from the model as untrusted: validate in `build_record()`.
- Model ID and pricing label live together in `src/config.py`; change both.
- New behaviour in `src/` gets a test in `tests/`.
- Never commit `.env`, `.streamlit/secrets.toml`, or real slips.

# QR Payment Ledger (PoC)

Upload screenshots of QR-payment confirmation slips (e.g. a Thai banking
app's "payment received" screen), extract structured payment data with
Claude's vision + tool use, review it in a table, and export it to CSV for
tax record-keeping.

This is Phase 1 — a proof of concept. It covers QR payment slips only, holds
records in memory for the session (no database), and is gated by a
lightweight shared-credentials login rather than real user accounts. See
`CLAUDE.md` for the full project plan.

## Documentation

| Doc | What's in it |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | User flow, module responsibilities, data model, design rules |
| [`docs/CODE_WALKTHROUGH.md`](docs/CODE_WALKTHROUGH.md) | File-by-file walkthrough: run order of `app.py`, the extraction call, `build_record`, tests and hooks |
| [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) | Dev setup, linting, tests, pre-commit hooks, conventions |
| [`docs/LINE_INTEGRATION.md`](docs/LINE_INTEGRATION.md) | Research: sending slips via a LINE Official Account (feasibility, law, plan) |
| [`CLAUDE.md`](CLAUDE.md) | Project brief and working agreement |

## Setup

1. **Create a virtual environment and install dependencies:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Set your API key:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set `ANTHROPIC_API_KEY` to your key from the
   [Anthropic Console](https://console.anthropic.com/settings/keys).

3. **Set login credentials:**

   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

   Edit `.streamlit/secrets.toml` and set a username/password for yourself
   and anyone else who should have access, under `[app_credentials]`. The
   app won't load without at least one entry here.

## Running the app

```bash
streamlit run app.py
```

This opens the app in your browser (usually `http://localhost:8501`).

**To test it:**

1. Log in with one of the username/password pairs from
   `.streamlit/secrets.toml`.
2. Drop one or more test slip screenshots (PNG or HEIC) into
   `sample_images/` — or just upload directly through the browser's file
   picker, they don't need to live in that folder first.
3. Use the "Upload slip screenshots" button in the app and select your
   image(s).
4. Wait for extraction to finish — each image makes one call to Claude, so a
   batch of a few images should take a few seconds each.
5. Review the table. Any row Claude flagged as `low` or `needs_review`
   confidence is highlighted and called out in a warning banner above the
   table — check those before trusting the export. Select rows and use the
   **Mark selected as DEBIT/RECEIPT** buttons to classify pay-outs vs.
   pay-ins.
6. Click **Download CSV** to export the current table. The file is built in
   memory and sent to your browser — nothing is written to the server's
   disk. It opens correctly in Excel, including Thai text.
7. The **Token usage** panel at the bottom shows API call count, total
   input/output tokens, and an estimated cost (pulled from Anthropic's
   current published pricing, not hardcoded).

Records only persist for the browser session — refreshing the page clears
the table. Re-uploading the same image won't reprocess it or spend extra
tokens as long as the session state hasn't been cleared. A file that fails
to process isn't marked as done, so you can re-upload it to retry.

## Deploying

[Streamlit Community Cloud](https://streamlit.io/cloud) is the easiest way
to run this live for free:

1. Push this repo to GitHub (`.env` and `.streamlit/secrets.toml` are
   gitignored, so your key and credentials won't be pushed).
2. On [share.streamlit.io](https://share.streamlit.io), create a new app
   pointing at this repo and `app.py`.
3. In the app's **Settings → Secrets**, paste the same contents as your
   local `.streamlit/secrets.toml` — `ANTHROPIC_API_KEY` plus an
   `[app_credentials]` table with a username/password for each person who
   should have access. This is what gates the live app: it's public in the
   sense that anyone with the URL can reach the login screen, but nobody
   gets past it without a valid password, so nobody but the people you've
   added can spend your API budget.

The login gate is intentionally simple — plain username/password pairs
compared server-side, no signup flow, no database. That's a reasonable
fit for a couple of named people; if this grows past a handful of users,
swap it for real accounts (Supabase Auth is the natural next step, since
Supabase is already the Phase 2 storage pick).

## Project layout

```
├── app.py                # Streamlit UI — the only file that touches the CLI/UI layer
├── sample_images/        # Drop test slips here (gitignored except .gitkeep)
├── output/                # Local CSV exports (gitignored except .gitkeep)
├── tests/                 # pytest suite — no network or API key needed
├── docs/                  # Architecture, development and LINE research docs
├── pyproject.toml         # ruff + pytest config
├── .pre-commit-config.yaml
└── src/
    ├── config.py          # Model ID, pricing label, account-digit limit
    ├── schema.py          # PaymentRecord, extraction tool schema, build_record()
    ├── image_loader.py    # Find + base64-encode images (HEIC → PNG conversion)
    ├── extractor.py       # Claude vision + tool-use call, one per image
    ├── token_tracker.py   # Accumulates token usage + estimates cost
    └── storage.py         # Records → DataFrame → CSV
```

## Development

```bash
pip install -r requirements-dev.txt
pre-commit install      # lint, format and test on every commit
pytest                  # run the tests
ruff check . && ruff format .
```

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for details.

## Notes

- Currency is fixed to THB for this PoC.
- Only the last four digits of any payer/recipient account number are ever
  stored — enforced in code by `build_record()`, not just requested in the
  prompt.
- `.env`, `.streamlit/secrets.toml`, and anything you drop in
  `sample_images/`/`output/` are gitignored since they can contain real
  bank details or credentials.

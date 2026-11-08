# CLAUDE.md — QR Payment Ledger (PoC)

## Project summary
A Python tool that ingests screenshots of QR-payment confirmation slips (e.g. a
Thai banking app's "payment received" screen), uses Claude's vision + tool use
to extract structured payment data, and shows a reviewable table with a CSV
export for tax record-keeping. This is Phase 1 — a proof of concept covering
QR payment slips only, with a basic upload-and-review UI. Scanned
invoices/receipts and a database are explicitly out of scope for this phase.

## Working agreement — read this first
This project exists primarily so Jason can learn Python and Anthropic's APIs
(vision, tool use, Files API, token usage). **Do not write full
implementations of the core learning functions.**

- Scaffold the file, add the function/class signature, a docstring describing
  inputs/outputs/behaviour, and a `# TODO` body — Jason fills these in.
- Boilerplate that isn't a learning target (folder structure, config files,
  CLI wiring in `main.py`, README) can be written in full.
- If Jason explicitly asks for a full implementation of something in the stub
  list, do it — but default to stubs.
- See "Scaffold vs. stub" below for exactly which files/functions fall in
  each bucket.

## Learning goals this maps to
- Image handling — multiple images, base64 encoding, MIME types
- Tools (tool use) — forcing structured JSON output instead of parsing prose
- Files API — upload once, reference by `file_id` (used lightly — see notes)
- Python fundamentals — dataclasses, file I/O, pandas, CSV, basic OOP
- Token tracking — reading `usage` off API responses and totalling it

## Assumptions — confirm before building
1. **Image type — confirmed**: uploads are phone screenshots of a banking
   app's payment-received confirmation screen ("slip"), in PNG or HEIC.
   Vision reads the text on the slip (amount, date, payer name, payer bank,
   masked account, reference).
   - Claude's vision API accepts JPEG, PNG, GIF, and WebP only — **not
     HEIC**. Any HEIC input has to be converted to PNG before it's sent, so
     `image_loader.py` needs a conversion step (`pillow-heif` is the usual
     choice) ahead of the base64 encode, not just a straight file read.
2. Single currency (THB) for the PoC.
3. "User name" = the **payer's** name on the receiving notification, not the
   shop's own account name. The shop's own receiving account (name, bank,
   masked account) is captured separately as `recipient_*` fields — useful
   for reconciliation when a shop has more than one receiving account, but
   optional since not every slip shows it as clearly as the payer side.
4. Deployed live (Streamlit Community Cloud) behind a lightweight
   username/password gate for a small, known set of people — a plain
   `[app_credentials]` table in Streamlit secrets, no signup flow, no
   database. Real user accounts (Supabase Auth is the natural fit, since
   Supabase is already the Phase 2 storage pick) are a later step, only
   worth it once this grows past a handful of named users.

## Non-goals for this phase
- Scanned invoices/receipts (Phase 2+)
- Database persistence (Phase 2 is Supabase — see below; PoC just holds
  records in memory for the session and writes CSV)
- Tax form generation / import
- Duplicate detection (confirmed as a Phase 2 item, not solved here)

## Looking ahead: monetisation & a mobile app
This PoC is the first phase of something you intend to grow into a paid
product with a mobile app — worth two small adjustments now, without
scope-creeping the PoC itself:
- **Keep `src/` free of CLI concerns.** Every function in `src/` should take
  plain arguments and return values — no `print()`, no `argparse`, no
  reading from stdin. `main.py` is the only place that touches the CLI.
  When there's eventually a backend or mobile app behind this, it calls the
  same `src/` functions `main.py` calls today — you're swapping the
  interface, not rewriting the core logic.
- **One forward-compatible schema field**: add `shop_id: str | None = None`
  to `PaymentRecord` now. It costs nothing today (stays `None`), and saves a
  schema migration once there's more than one shop or user.

**Phase 2 storage is settled: Supabase.** That fits well with what's already
here — `shop_id` maps directly onto a Supabase Auth user/org ID once that
exists, and because `storage.py` is the only module that knows about CSV,
swapping it for a Supabase client later is a one-module change, not a
restructure. Supabase Storage would also replace `sample_images/`/`output/`
for the mobile-upload phase. None of that needs building now — the point of
today's structure is just that it won't fight you when you get there.

Everything else — auth, an API layer, the mobile app itself — stays out of
scope for this repo until you're actually building it.

## Architecture
```
qr-payment-tracker/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── app.py                # Streamlit UI — upload, table, CSV download
├── sample_images/        # gitignored except .gitkeep — test slips go here
├── output/               # gitignored — CSV exports land here
├── tests/                # pytest suite (no network / API key needed)
├── docs/                 # ARCHITECTURE.md, DEVELOPMENT.md, LINE_INTEGRATION.md
├── pyproject.toml        # ruff + pytest config
├── .pre-commit-config.yaml
└── src/
    ├── __init__.py
    ├── config.py         # model ID, pricing label, account-digit limit
    ├── schema.py         # PaymentRecord, extraction tool schema, build_record()
    ├── image_loader.py   # find + base64-encode images
    ├── extractor.py      # Claude vision + tool-use call, one per image
    ├── token_tracker.py  # accumulates usage across calls
    └── storage.py        # records -> DataFrame -> CSV
```

## Data model (`src/schema.py`)
```python
@dataclass
class PaymentRecord:
    source_filename: str
    transaction_date: str            # ISO 8601, e.g. "2026-08-14"
    transaction_time: str | None
    amount: float
    currency: str                    # default "THB"
    payer_name: str | None
    payer_bank: str | None
    payer_account_last_digits: str | None
    recipient_name: str | None        # the shop's own name as shown on the slip
    recipient_bank: str | None
    recipient_account_last_digits: str | None
    reference_number: str | None
    extraction_confidence: str       # "high" | "low" | "needs_review"
    notes: str | None                # anything Claude flagged as uncertain
    shop_id: str | None = None       # forward-compat placeholder for the future multi-shop/SaaS phase
    transaction_type: str | None = None  # "DEBIT" (pay-out) | "RECEIPT" (pay-in) | None (unclassified)
```
This should map close to 1:1 onto the extraction tool's JSON schema, so
turning a `tool_use` block back into a `PaymentRecord` is mostly plumbing.
`transaction_type` is the one exception — it's not extracted by Claude, it's
set by the user in the review UI (bulk row-select in the table, then a
DEBIT/RECEIPT button), so people can tell pay-ins from pay-outs at a glance.

## Scaffold vs. stub

| File | Claude Code writes... |
|---|---|
| Repo scaffolding, `requirements.txt`, `.env.example`, `.gitignore`, `README.md` | **Full** |
| `src/schema.py` — `PaymentRecord` dataclass | **Full** (fields above) |
| `src/schema.py` — extraction tool JSON schema | **Stub** — Jason writes this against the Tools docs, using the dataclass as a guide |
| `src/image_loader.py` — `find_images(folder)`, `encode_image(path)` (incl. HEIC→PNG conversion) | **Stub** |
| `src/extractor.py` — `extract_from_image(client, path, tool_schema)` | **Stub** — leave a comment sketching the shape of the `messages.create()` call (model, image content block, `tools`, `tool_choice`), body is TODO |
| `src/token_tracker.py` — `TokenTracker` class | **Stub** — attributes + method signatures (`record()`, `summary()`, `total_tokens`), no logic |
| `src/storage.py` — `to_dataframe()`, `export_csv()` | **Stub** |
| `app.py` — Streamlit UI wiring everything together | **Full** — this is the map that shows how the stubbed pieces fit |

## Build order
1. Scaffold the repo (structure, config, `.gitignore`, `requirements.txt` —
   `anthropic`, `pandas`, `python-dotenv`, `pillow-heif` for HEIC conversion,
   `streamlit` for the UI).
2. `src/schema.py`: full `PaymentRecord` dataclass; stub the tool schema.
3. `src/image_loader.py`: stub `find_images()`, `encode_image()`.
4. `src/extractor.py`: stub `extract_from_image()` with a comment showing
   where the image content block, tool definition, and
   `tool_choice={"type": "tool", "name": ...}` go.
5. `src/token_tracker.py`: stub `TokenTracker`.
6. `src/storage.py`: stub `to_dataframe()` / `export_csv()`.
7. `app.py`: wire it together — `st.file_uploader(accept_multiple_files=True)`
   for the images, call the extractor per file, feed the tracker, collect
   records into `st.session_state` (Streamlit reruns the whole script on
   every interaction, so state has to be held explicitly or it resets),
   render the table with `st.dataframe`, show the token summary, and a
   `st.download_button` for the CSV.
8. `README.md`: setup, how to run, where to drop test slips.

## Definition of done for the PoC
Running `streamlit run app.py`:
- Lets you upload one or more slip images (PNG/HEIC) through the browser
- Shows a table with every `PaymentRecord` field once processing finishes
- Flags any low-confidence extraction visibly, not silently included
- Has a button to download the current table as CSV
- Shows a token usage summary (call count, total input/output tokens, a
  cost estimate pulled from current published per-token pricing — don't
  hardcode a rate, it'll go stale)

## Notes on the specific tools
- **Vision**: one image per `messages.create()` call — keeps extraction
  focused and keeps token tracking simple to reason about (image in, tool
  call out).
- **Tools**: use `tool_choice` to force the extraction tool call rather than
  a prose reply — that's what makes output reliably parseable.
- **Files API** (`client.beta.files.upload()`, beta header
  `files-api-2025-04-14`): not essential here since each image is only
  referenced once. Worth using deliberately once you're re-running the same
  image against different prompts while debugging, or later feeding a batch
  into the code execution tool. Fine to skip for the PoC — this is a
  later-phase feature of the *same* project (the natural fit is once a
  mobile app is uploading images through a backend: upload once server-side
  instead of round-tripping base64 through the API on every extraction
  call), not something that needs its own repo.
- **Code execution tool**: runs server-side in Anthropic's sandbox with no
  access to your local filesystem — wrong tool for "process files in my
  local folder." Could fit a later feature like "ask Claude questions about
  the exported ledger" in the eventual app. Same answer: later phase, same
  project, skip for the PoC.

## Security / privacy
- `.env` (holds `ANTHROPIC_API_KEY`) and anything under `sample_images/` /
  `output/` with real data must be gitignored — this is real bank detail.
- Never store more than the last few digits of an account number — hard
  constraint, not a nice-to-have.

"""Streamlit UI: upload QR payment slips, extract via Claude vision, review, export CSV.

This is the only place in the project that touches the CLI/UI layer — every
function it calls into (src/extractor.py, src/storage.py, ...) takes plain
arguments and returns values, so a future backend or mobile app can call the
same functions this file calls today.
"""

import hashlib
import hmac
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

from src.extractor import extract_from_image
from src.image_loader import SUPPORTED_EXTENSIONS
from src.schema import EXTRACTION_TOOL, PaymentRecord
from src.storage import export_csv, to_dataframe
from src.token_tracker import TokenTracker

load_dotenv()

OUTPUT_CSV_PATH = Path("output") / "ledger.csv"
FLAGGED_CONFIDENCE_LEVELS = {"low", "needs_review"}


def _file_key(uploaded_file) -> str:
    """Stable key for an uploaded file so a Streamlit rerun doesn't reprocess it."""
    digest = hashlib.md5(uploaded_file.getvalue()).hexdigest()
    return f"{uploaded_file.name}:{uploaded_file.size}:{digest}"


def _build_record(filename: str, fields: dict) -> PaymentRecord:
    """Combine an extraction tool's output with the source filename.

    Uses .get() for everything but source_filename since `fields` comes
    from the model's tool call — an external boundary — and the schema
    only marks a few fields required; anything else can legitimately be
    absent rather than present-but-null.
    """
    return PaymentRecord(
        source_filename=filename,
        transaction_date=fields.get("transaction_date"),
        transaction_time=fields.get("transaction_time"),
        amount=fields.get("amount"),
        currency=fields.get("currency", "THB"),
        payer_name=fields.get("payer_name"),
        payer_bank=fields.get("payer_bank"),
        payer_account_last_digits=fields.get("payer_account_last_digits"),
        recipient_name=fields.get("recipient_name"),
        recipient_bank=fields.get("recipient_bank"),
        recipient_account_last_digits=fields.get("recipient_account_last_digits"),
        reference_number=fields.get("reference_number"),
        extraction_confidence=fields.get("extraction_confidence", "needs_review"),
        notes=fields.get("notes"),
    )


def _get_credentials() -> dict[str, str]:
    """Load username -> password pairs from Streamlit secrets.

    Returns an empty dict rather than raising when .streamlit/secrets.toml
    doesn't exist yet (local dev before first setup) — the caller shows a
    clear setup message instead of a raw traceback.
    """
    try:
        return dict(st.secrets.get("app_credentials", {}))
    except StreamlitSecretNotFoundError:
        return {}


def _require_login() -> None:
    """Gate the whole app behind a username/password check.

    Credentials live in st.secrets["app_credentials"] (see
    .streamlit/secrets.toml.example) — set locally in
    .streamlit/secrets.toml (gitignored) or via Streamlit Community
    Cloud's Secrets panel when deployed. Not meant to scale past a
    handful of named people; add real accounts (e.g. Supabase Auth)
    before this app has more than a few users.
    """
    if st.session_state.get("authenticated"):
        return

    st.title("QR Payment Ledger")
    credentials = _get_credentials()
    if not credentials:
        st.error(
            "No login credentials configured. Add an [app_credentials] table to "
            ".streamlit/secrets.toml (see .streamlit/secrets.toml.example)."
        )
        st.stop()

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        expected_password = credentials.get(username)
        if expected_password is not None and hmac.compare_digest(password, expected_password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.stop()


st.set_page_config(page_title="QR Payment Ledger", layout="wide")
_require_login()

with st.sidebar:
    st.caption(f"Logged in as **{st.session_state.username}**")
    if st.button("Log out"):
        st.session_state.authenticated = False
        st.rerun()

st.title("QR Payment Ledger")
st.caption(
    "Upload payment-received slip screenshots to extract a reviewable, "
    "exportable table for tax record-keeping."
)

if "records" not in st.session_state:
    st.session_state.records = []
if "processed_file_keys" not in st.session_state:
    st.session_state.processed_file_keys = set()
if "tracker" not in st.session_state:
    st.session_state.tracker = TokenTracker()

try:
    client = Anthropic()
except Exception as exc:
    st.error(
        "Could not initialize the Anthropic client — set ANTHROPIC_API_KEY in "
        f"a .env file (see .env.example). ({exc})"
    )
    st.stop()

uploaded_files = st.file_uploader(
    "Upload slip screenshots",
    type=sorted(ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS),
    accept_multiple_files=True,
)

if uploaded_files:
    new_files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if _file_key(uploaded_file) not in st.session_state.processed_file_keys
    ]
    if new_files:
        progress = st.progress(0.0, text="Extracting payment details...")
        for i, uploaded_file in enumerate(new_files):
            suffix = Path(uploaded_file.name).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = Path(tmp.name)
            try:
                fields, usage = extract_from_image(client, tmp_path, EXTRACTION_TOOL)
                st.session_state.tracker.record(usage)
                st.session_state.records.append(_build_record(uploaded_file.name, fields))
            except Exception as exc:
                st.error(f"Failed to process {uploaded_file.name}: {exc}")
            finally:
                tmp_path.unlink(missing_ok=True)
            st.session_state.processed_file_keys.add(_file_key(uploaded_file))
            progress.progress((i + 1) / len(new_files), text=f"Processed {uploaded_file.name}")
        progress.empty()

st.subheader("Extracted payments")

if st.session_state.records:
    df = to_dataframe(st.session_state.records)

    flagged = df["extraction_confidence"].isin(FLAGGED_CONFIDENCE_LEVELS)
    if flagged.any():
        flagged_names = ", ".join(df.loc[flagged, "source_filename"])
        st.warning(f"{flagged.sum()} record(s) need review before exporting: {flagged_names}")

    def _highlight_flagged(row: pd.Series) -> list[str]:
        style = "background-color: #fff3cd" if row["extraction_confidence"] in FLAGGED_CONFIDENCE_LEVELS else ""
        return [style] * len(row)

    selection = st.dataframe(
        df.style.apply(_highlight_flagged, axis=1),
        column_config={
            "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
            "transaction_type": st.column_config.TextColumn("Type"),
        },
        on_select="rerun",
        selection_mode="multi-row",
        key="ledger_table",
    )
    selected_rows = selection.selection.rows

    st.caption(
        f"{len(selected_rows)} row(s) selected — select rows above, then classify them as a"
        " pay-in (RECEIPT) or pay-out (DEBIT)."
        if selected_rows
        else "Select one or more rows above to bulk-classify them as DEBIT or RECEIPT."
    )
    debit_col, receipt_col = st.columns(2)
    with debit_col:
        if st.button("Mark selected as DEBIT", disabled=not selected_rows, width="stretch"):
            for row in selected_rows:
                st.session_state.records[row].transaction_type = "DEBIT"
            st.rerun()
    with receipt_col:
        if st.button("Mark selected as RECEIPT", disabled=not selected_rows, width="stretch"):
            for row in selected_rows:
                st.session_state.records[row].transaction_type = "RECEIPT"
            st.rerun()

    csv_path = export_csv(df, OUTPUT_CSV_PATH)
    st.download_button(
        "Download CSV",
        data=csv_path.read_bytes(),
        file_name="ledger.csv",
        mime="text/csv",
    )
else:
    st.info("Upload one or more slip images to get started.")

st.subheader("Token usage")
summary = st.session_state.tracker.summary()
col1, col2, col3, col4 = st.columns(4)
col1.metric("API calls", summary["call_count"])
col2.metric("Input tokens", f"{summary['total_input_tokens']:,}")
col3.metric("Output tokens", f"{summary['total_output_tokens']:,}")
if summary.get("estimated_cost_usd") is not None:
    col4.metric("Estimated cost", f"${summary['estimated_cost_usd']:.4f}")
else:
    col4.metric("Estimated cost", "N/A")
    st.caption(f"Cost estimate unavailable: {summary.get('pricing_error', 'unknown error')}")

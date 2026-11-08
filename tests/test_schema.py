from src.schema import build_record

GOOD = {
    "transaction_date": "2026-08-14",
    "amount": 250,
    "currency": "THB",
    "extraction_confidence": "high",
}


def test_build_record_happy_path():
    record = build_record("slip.png", {**GOOD, "payer_name": "Somchai"})
    assert record.source_filename == "slip.png"
    assert record.amount == 250.0
    assert record.extraction_confidence == "high"
    assert record.transaction_type is None
    assert record.notes is None


def test_account_digits_truncated_to_last_four():
    record = build_record("slip.png", {**GOOD, "payer_account_last_digits": "xxx-x-x1234-5678"})
    assert record.payer_account_last_digits == "5678"
    assert "truncated" in record.notes


def test_masked_digits_kept():
    record = build_record("slip.png", {**GOOD, "recipient_account_last_digits": "XXX-X-X5678-X"})
    assert record.recipient_account_last_digits == "5678"
    assert record.notes is None


def test_missing_amount_forces_needs_review():
    fields = {k: v for k, v in GOOD.items() if k != "amount"}
    record = build_record("slip.png", fields)
    assert record.amount is None
    assert record.extraction_confidence == "needs_review"


def test_unparseable_amount_forces_needs_review():
    record = build_record("slip.png", {**GOOD, "amount": "abc"})
    assert record.extraction_confidence == "needs_review"


def test_model_notes_are_preserved():
    record = build_record("slip.png", {**GOOD, "notes": "blurry reference"})
    assert record.notes == "blurry reference"

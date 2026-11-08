from dataclasses import fields

import pandas as pd

from src.schema import PaymentRecord, build_record
from src.storage import export_csv, to_csv_bytes, to_dataframe


def _record():
    return build_record(
        "slip.png",
        {
            "transaction_date": "2026-08-14",
            "amount": 99.5,
            "currency": "THB",
            "payer_name": "สมชาย",
            "extraction_confidence": "high",
        },
    )


def test_dataframe_columns_match_dataclass_order():
    df = to_dataframe([_record()])
    assert list(df.columns) == [f.name for f in fields(PaymentRecord)]


def test_empty_records_gives_empty_frame_with_columns():
    df = to_dataframe([])
    assert df.empty
    assert "amount" in df.columns


def test_export_csv_creates_parent_dir(tmp_path):
    out = export_csv(to_dataframe([_record()]), tmp_path / "nested" / "ledger.csv")
    assert out.exists()
    assert pd.read_csv(out).loc[0, "amount"] == 99.5


def test_csv_bytes_have_bom_and_thai_text():
    data = to_csv_bytes(to_dataframe([_record()]))
    assert data.startswith(b"\xef\xbb\xbf")
    assert "สมชาย" in data.decode("utf-8-sig")

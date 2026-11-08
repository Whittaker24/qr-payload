"""Turn PaymentRecords into a DataFrame and export them to CSV."""

from dataclasses import asdict, fields
from pathlib import Path

import pandas as pd

from src.schema import PaymentRecord


def to_dataframe(records: list[PaymentRecord]) -> pd.DataFrame:
    """Convert a list of PaymentRecords into a pandas DataFrame.

    Args:
        records: Extracted payment records, in the order they should be
            displayed/exported (e.g. upload order).

    Returns:
        A DataFrame with one row per record and one column per
        PaymentRecord field (source_filename, transaction_date, ...,
        shop_id). Column order should match the dataclass field order.
    """
    columns = [field.name for field in fields(PaymentRecord)]
    rows = [asdict(record) for record in records]
    return pd.DataFrame(rows, columns=columns)


def export_csv(df: pd.DataFrame, output_path: str | Path) -> Path:
    """Write a DataFrame to CSV.

    Args:
        df: The DataFrame to export (as returned by to_dataframe()).
        output_path: Where to write the CSV, e.g. output/ledger.csv.

    Returns:
        The Path the CSV was written to.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialise a DataFrame to CSV bytes without touching disk.

    Encoded as UTF-8 with a BOM so Excel displays Thai text correctly.

    Preferred for downloads: on a shared host a fixed output path would be
    overwritten between users and leave bank data on the server's disk.
    """
    return df.to_csv(index=False).encode("utf-8-sig")

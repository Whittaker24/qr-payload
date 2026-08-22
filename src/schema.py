"""Data model and extraction tool schema for QR payment slips."""

from dataclasses import dataclass


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
    # User-assigned in the review UI (not extracted by Claude): "DEBIT" (pay-out)
    # | "RECEIPT" (pay-in) | None (not yet classified).
    transaction_type: str | None = None


# JSON schema for the tool Claude calls to return extracted payment data.
# Passed as `input_schema` in a tool definition to `messages.create(tools=[...])`.
# Maps 1:1 onto PaymentRecord's fields, minus source_filename (the caller
# already knows the filename) and shop_id (not something Claude can read
# off the slip). Recipient fields are the shop's own receiving account as
# shown on the slip — separate from the payer fields (assumption #3 in
# CLAUDE.md), and often less complete since not every slip shows the
# recipient's masked account number.
EXTRACTION_TOOL = {
    "name": "extract_payment_record",
    "description": (
        "Extract structured payment data from a QR payment confirmation "
        "slip screenshot (e.g. a Thai banking app's 'payment received' "
        "screen)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "transaction_date": {
                "type": "string",
                "description": "Date the payment was made, ISO 8601 format, e.g. \"2026-08-14\".",
            },
            "transaction_time": {
                "type": ["string", "null"],
                "description": "Time the payment was made, e.g. \"14:32\". Null if not visible on the slip.",
            },
            "amount": {
                "type": "number",
                "description": "Payment amount as a number, e.g. 250.00.",
            },
            "currency": {
                "type": "string",
                "description": "Three-letter currency code. Always \"THB\" for this PoC.",
            },
            "payer_name": {
                "type": ["string", "null"],
                "description": "Name of the payer (the person who sent the payment), not the shop's own account name.",
            },
            "payer_bank": {
                "type": ["string", "null"],
                "description": "Name of the payer's bank, e.g. \"Kasikorn Bank\".",
            },
            "payer_account_last_digits": {
                "type": ["string", "null"],
                "description": "Last few digits only of the payer's masked account number. Never the full number.",
            },
            "recipient_name": {
                "type": ["string", "null"],
                "description": "Name of the recipient (the shop's own account name) as shown on the slip, e.g. under 'To' or 'Pay to'. Null if not shown.",
            },
            "recipient_bank": {
                "type": ["string", "null"],
                "description": "Name of the recipient's (shop's) bank, e.g. \"Kasikorn Bank\". Null if not shown.",
            },
            "recipient_account_last_digits": {
                "type": ["string", "null"],
                "description": "Last few digits only of the recipient's (shop's) masked account number, if shown. Never the full number.",
            },
            "reference_number": {
                "type": ["string", "null"],
                "description": "Transaction reference number shown on the slip, if any.",
            },
            "extraction_confidence": {
                "type": "string",
                "enum": ["high", "low", "needs_review"],
                "description": "How confident the extraction is. Use \"low\" or \"needs_review\" if any field was unclear, blurry, or ambiguous.",
            },
            "notes": {
                "type": ["string", "null"],
                "description": "Anything uncertain or worth flagging for human review. Null if nothing to note.",
            },
        },
        "required": [
            "transaction_date",
            "amount",
            "currency",
            "extraction_confidence",
        ],
    },
}
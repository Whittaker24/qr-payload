from types import SimpleNamespace

from src import token_tracker
from src.token_tracker import PricingUnavailableError, TokenTracker


def _usage(i, o):
    return SimpleNamespace(input_tokens=i, output_tokens=o)


def test_record_accumulates():
    tracker = TokenTracker()
    tracker.record(_usage(100, 20))
    tracker.record(_usage(50, 5))
    assert tracker.call_count == 2
    assert tracker.total_tokens == 175


def test_summary_estimates_cost(monkeypatch):
    monkeypatch.setattr(token_tracker, "_published_rates_usd_per_mtok", lambda: (2.0, 10.0))
    tracker = TokenTracker()
    tracker.record(_usage(1_000_000, 100_000))
    assert tracker.summary()["estimated_cost_usd"] == 3.0


def test_summary_survives_pricing_failure(monkeypatch):
    def boom():
        raise PricingUnavailableError("offline")

    monkeypatch.setattr(token_tracker, "_published_rates_usd_per_mtok", boom)
    tracker = TokenTracker()
    tracker.record(_usage(10, 1))
    summary = tracker.summary()
    assert summary["estimated_cost_usd"] is None
    assert summary["pricing_error"] == "offline"
    assert summary["total_input_tokens"] == 10


# Trimmed copy of the standard table from the published pricing page, plus the
# Batch table below it (same model, half the price) that must not be matched.
PRICING_PAGE = """\
| Model             | Base input tokens | 5m cache writes | 1h cache writes | Cache hits and refreshes | Output tokens |
| ----------------- | ----------------- | --------------- | --------------- | ------------------------ | ------------- |
| Claude Sonnet 5.5 | $2 / MTok         | $2.50 / MTok    | $4 / MTok       | $0.10 / MTok<sup>2</sup> | $10 / MTok    |
| Claude Sonnet 5   | $2 / MTok<sup>3</sup> | $2.50 / MTok | $4 / MTok       | $0.20 / MTok             | $10 / MTok<sup>3</sup> |

| Model             | Batch input | Batch output |
| ----------------- | ----------- | ------------ |
| Claude Sonnet 5.5 | $1 / MTok   | $5 / MTok    |
"""


def test_parse_rates_reads_standard_table_not_batch():
    assert token_tracker._parse_rates(PRICING_PAGE) == (2.0, 10.0)


def test_parse_rates_does_not_confuse_sonnet_5_with_5_5(monkeypatch):
    monkeypatch.setattr(token_tracker, "PRICING_MODEL_LABEL", "Claude Sonnet 5")
    assert token_tracker._parse_rates(PRICING_PAGE) == (2.0, 10.0)


def test_parse_rates_raises_when_table_missing():
    import pytest

    with pytest.raises(PricingUnavailableError):
        token_tracker._parse_rates("no tables here")

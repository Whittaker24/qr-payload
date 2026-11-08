"""Accumulates Claude API token usage across extraction calls."""

import re
import ssl
from dataclasses import dataclass
from functools import lru_cache
from urllib.error import URLError
from urllib.request import Request, urlopen

import certifi
from anthropic.types import Usage

from src.config import PRICING_MODEL_LABEL

# Live published rates for config.MODEL (labelled PRICING_MODEL_LABEL in the table).
# .md gives the docs as plain text so we can parse them without scraping HTML.
PRICING_URL = "https://platform.claude.com/docs/en/about-claude/pricing.md"
TOKENS_PER_MTOK = 1_000_000

# The standard pricing table's header row. Anchoring on this (rather than
# just searching the whole page for the model name) matters because the
# page also has a separate Batch API table further down with the same
# model name at half the price — without this anchor, a page reorg could
# make us silently match the wrong table.
_PRICING_TABLE_HEADER = re.compile(r"\|\s*Model\s*\|.*Output Tokens.*\|", re.IGNORECASE)


class PricingUnavailableError(RuntimeError):
    """Raised when current Claude API pricing can't be fetched or parsed.

    Callers (e.g. the Streamlit UI) should catch this and show a
    "cost estimate unavailable" message rather than letting it propagate —
    losing network access to the pricing page shouldn't take down the
    whole token-usage summary.
    """


@lru_cache(maxsize=1)
def _published_rates_usd_per_mtok() -> tuple[float, float]:
    """Return (input, output) USD per million tokens from Anthropic's pricing page.

    Cached after the first successful fetch so Streamlit reruns do not
    hit the network every time the UI redraws. Raises
    PricingUnavailableError (never a raw urllib/parsing exception) so
    callers have one exception type to handle.
    """
    return _parse_rates(_fetch_pricing_page())


def _fetch_pricing_page() -> str:
    """Download the pricing page as markdown text."""
    request = Request(PRICING_URL, headers={"User-Agent": "qr-payment-tracker/0.1"})
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=10, context=context) as response:
            return response.read().decode("utf-8")
    except (URLError, TimeoutError, OSError) as exc:
        raise PricingUnavailableError(f"Could not reach {PRICING_URL}: {exc}") from exc


def _parse_rates(page: str) -> tuple[float, float]:
    """Extract (input, output) USD per MTok for PRICING_MODEL_LABEL from the pricing markdown."""
    # Scope the row search to the standard pricing table only — start
    # right after its header row and stop at the first blank line (the
    # table's end), so the Batch API table can't be matched by mistake.
    header_match = _PRICING_TABLE_HEADER.search(page)
    if header_match is None:
        raise PricingUnavailableError(f"Could not find the standard pricing table on {PRICING_URL}")
    table_end = page.find("\n\n", header_match.end())
    table = page[header_match.end() : table_end if table_end != -1 else None]

    # Docs pad the model column with spaces: "| Claude Sonnet 5     | $2 / MTok | ... |"
    row = re.search(
        rf"\| {re.escape(PRICING_MODEL_LABEL)}\s+\|((?:[^|\n]+\|)+)",
        table,
    )
    if row is None:
        raise PricingUnavailableError(
            f"Could not find {PRICING_MODEL_LABEL} in the standard pricing table on {PRICING_URL}"
        )

    # The row has one price column per pricing dimension (base input,
    # cache writes/reads, output) — regardless of how many cache columns
    # sit in between, the first price is always base input and the last
    # is always output.
    prices = [float(value) for value in re.findall(r"\$([0-9.]+)", row.group(1))]
    if len(prices) < 2:
        raise PricingUnavailableError(f"Could not parse {PRICING_MODEL_LABEL} rates from {PRICING_URL}")

    return prices[0], prices[-1]


@dataclass
class TokenTracker:
    """Tracks token usage and call count across multiple extract_from_image() calls.

    Attributes:
        call_count: Number of extraction calls recorded so far.
        total_input_tokens: Sum of input_tokens across all recorded calls.
        total_output_tokens: Sum of output_tokens across all recorded calls.
    """

    call_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def record(self, usage: Usage) -> None:
        """Add one API call's usage to the running totals.

        Args:
            usage: The `usage` object from a messages.create() response
                (has .input_tokens and .output_tokens).
        """
        self.call_count += 1
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens

    def summary(self) -> dict[str, int | float]:
        """Return a summary of accumulated usage for display in the UI.

        Returns:
            A dict with at least: call_count, total_input_tokens,
            total_output_tokens, and an estimated_cost_usd figure. Pull the
            per-token rate from current published pricing rather than
            hardcoding it — see CLAUDE.md's note on not hardcoding a rate,
            since it'll go stale.

            If the current pricing can't be fetched (offline, docs page
            unreachable/reformatted), estimated_cost_usd is None and
            pricing_error holds a human-readable reason — the token counts
            themselves are still returned, since those don't depend on
            the network.
        """
        base = {
            "call_count": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }
        try:
            input_usd_per_mtok, output_usd_per_mtok = _published_rates_usd_per_mtok()
        except PricingUnavailableError as exc:
            return {
                **base,
                "estimated_cost_usd": None,
                "pricing_error": str(exc),
            }

        estimated_cost_usd = (
            self.total_input_tokens / TOKENS_PER_MTOK * input_usd_per_mtok
            + self.total_output_tokens / TOKENS_PER_MTOK * output_usd_per_mtok
        )
        return {
            **base,
            "estimated_cost_usd": estimated_cost_usd,
            "input_usd_per_mtok": input_usd_per_mtok,
            "output_usd_per_mtok": output_usd_per_mtok,
        }

    @property
    def total_tokens(self) -> int:
        """Total input + output tokens recorded so far."""
        return self.total_input_tokens + self.total_output_tokens

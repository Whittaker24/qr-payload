"""Settings shared across modules. Keep the model and its pricing label together so they can't drift."""

# Model used for extraction.
MODEL = "claude-sonnet-5-5"
# How the same model is named in Anthropic's published pricing table
# (parsed by token_tracker.py). Update both together when changing MODEL.
PRICING_MODEL_LABEL = "Claude Sonnet 5.5"

# Hard constraint (CLAUDE.md > Security): never store more than this many
# trailing digits of an account number.
MAX_ACCOUNT_DIGITS = 4

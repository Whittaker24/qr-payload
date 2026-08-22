"""Claude vision + tool-use call to extract payment data from a slip image."""

from pathlib import Path
from typing import Any

from anthropic import Anthropic
from anthropic.types import Usage

from src.image_loader import encode_image

MODEL = "claude-sonnet-5"


def extract_from_image(
    client: Anthropic, path: str | Path, tool_schema: dict
) -> tuple[dict[str, Any], Usage]:
    """Extract structured payment data from a single slip image.

    Encodes the image, sends it to Claude in one messages.create() call
    with `tool_schema` as the only available tool, and forces Claude to
    call it (rather than reply in prose) via `tool_choice`. One image per
    call — keeps extraction focused and keeps token tracking simple to
    reason about (image in, tool call out).

    Args:
        client: An initialized Anthropic client.
        path: Path to a single slip image (PNG/JPEG/HEIC/etc — HEIC is
            converted to PNG by encode_image() before it's sent).
        tool_schema: The extraction tool definition (EXTRACTION_TOOL from
            src/schema.py) — passed as the sole entry in `tools`.

    Returns:
        A (fields, usage) tuple:
        - fields: the tool_use block's `input` dict, i.e. the extracted
          payment fields as Claude returned them (transaction_date,
          amount, etc — everything in tool_schema except source_filename).
          The caller combines this with the filename to build a
          PaymentRecord.
        - usage: the response's `usage` object (input_tokens,
          output_tokens), for TokenTracker to record.
    """
    base64_data, media_type = encode_image(path)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": tool_schema["name"]},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract the payment details from this slip.",
                    },
                ],
            }
        ],
    )

    # tool_choice forces a tool_use block; walk content in case a text
    # block is also present.
    for block in response.content:
        if block.type == "tool_use":
            return block.input, response.usage

    raise ValueError("Claude response contained no tool_use block")

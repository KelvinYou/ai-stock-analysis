from __future__ import annotations

import asyncio
import logging
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

logger = logging.getLogger(__name__)


async def query_with_retry(
    *,
    prompt: str,
    options: ClaudeAgentOptions,
    attempts: int = 5,
    backoff_s: float = 3.0,
    label: str = "query",
) -> ResultMessage:
    """Run an SDK query, retrying on transient CLI subprocess failures.

    The claude-agent-sdk occasionally surfaces `Command failed with exit code 1`
    from the underlying subprocess even when the request is well-formed —
    especially on haiku. We retry with exponential backoff and return the
    first ResultMessage we receive.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result_msg: ResultMessage | None = None
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    result_msg = message
            if result_msg is None:
                raise RuntimeError(f"{label}: no ResultMessage returned")
            return result_msg
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == attempts:
                break
            sleep_s = backoff_s * (2 ** (attempt - 1))
            logger.warning(
                "%s attempt %d/%d failed: %s — retrying in %.1fs",
                label,
                attempt,
                attempts,
                str(exc)[:160],
                sleep_s,
            )
            await asyncio.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


def extract_structured(msg: ResultMessage) -> dict[str, Any] | str | None:
    """Return structured_output dict, else raw result text, else None."""
    if msg.structured_output:
        return msg.structured_output
    if msg.result:
        return msg.result
    return None

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    SdkMcpTool,
    create_sdk_mcp_server,
)
from pydantic import BaseModel

from stock_analysis._query_retry import query_with_retry
from stock_analysis.models.market_data import TickerData


class BaseAnalystAgent(ABC):
    """Base class for all Layer 2 analyst agents.

    Each agent gets:
    - A system prompt defining its analyst persona
    - Custom MCP tools providing market data
    - A Pydantic output schema for structured JSON output
    """

    name: str
    description: str
    model: str  # "haiku", "sonnet", "opus"

    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def build_tools(self, ticker_data: TickerData) -> list[SdkMcpTool]: ...

    @abstractmethod
    def output_model(self) -> type[BaseModel]: ...

    async def analyze(self, ticker_data: TickerData) -> BaseModel:
        """Run the agent and return a validated Pydantic model."""
        tools = self.build_tools(ticker_data)
        server = create_sdk_mcp_server(name=self.name, tools=tools)
        tool_names = [f"mcp__{self.name}__{t.name}" for t in tools]

        schema = self.output_model().model_json_schema()

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=self.system_prompt(),
            mcp_servers={self.name: server},
            allowed_tools=tool_names,
            permission_mode="bypassPermissions",
            output_format={"type": "json_schema", "schema": schema},
            max_turns=5,
        )

        prompt = (
            f"Analyze the stock {ticker_data.info.symbol} ({ticker_data.info.name}). "
            f"Use the available tools to retrieve the data you need, then produce your analysis. "
            f"Sector: {ticker_data.info.sector or 'Unknown'}. "
            f"Industry: {ticker_data.info.industry or 'Unknown'}."
        )

        result_json: dict[str, Any] | None = None
        result_text: str | None = None
        message = await query_with_retry(
            prompt=prompt, options=options, label=f"{self.name}-agent"
        )
        if message.structured_output:
            result_json = message.structured_output
        elif message.result:
            result_text = message.result

        if result_json is not None:
            return self.output_model().model_validate(result_json)

        # Fallback: parse JSON from result text
        if result_text:
            return self.output_model().model_validate_json(result_text)

        raise RuntimeError(f"{self.name} agent failed to produce structured output")

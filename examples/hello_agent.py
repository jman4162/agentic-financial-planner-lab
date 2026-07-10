"""Minimal Strands agent wired to one deterministic calculator tool.

Demonstrates the project's core rule: the LLM orchestrates and explains,
deterministic code does the math. Requires a local Ollama server
(https://ollama.com/), the `agent` extra installed, and a model with
reliable tool-calling (small models like llama3.2 tend to fabricate
tool arguments or emit tool calls as text).

Usage:
    uv run python examples/hello_agent.py
    OLLAMA_MODEL=gpt-oss:20b uv run python examples/hello_agent.py
"""

import os

from strands import Agent, tool
from strands.models.ollama import OllamaModel

from planner_lab.calculators import funded_ratio as _funded_ratio


@tool
def funded_ratio(
    portfolio_value: float,
    annual_spending: float,
    withdrawal_rate: float = 0.04,
) -> dict:
    """Compute the funded ratio: portfolio value divided by the capital needed
    to support annual spending at the given withdrawal rate.

    A ratio of 1.0 means the portfolio exactly covers the spending target;
    below 1.0 means a shortfall. This is a point-in-time diagnostic, not a
    guarantee of retirement success.

    Args:
        portfolio_value: Current investable assets in dollars.
        annual_spending: Target annual retirement spending in dollars.
        withdrawal_rate: Assumed sustainable withdrawal rate as a decimal
            fraction. Omit this argument unless the user specified a rate;
            the default is 0.04 (the 4% guideline).
    """
    return _funded_ratio(portfolio_value, annual_spending, withdrawal_rate)


SYSTEM_PROMPT = """\
You are an educational financial planning assistant. You never perform
arithmetic yourself: call the provided tools for every calculation and
report their outputs, including the assumptions they used. State clearly
that this is educational analysis, not financial advice.
"""


def main() -> None:
    model = OllamaModel(
        host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        model_id=os.environ.get("OLLAMA_MODEL", "qwen3"),
    )
    agent = Agent(model=model, tools=[funded_ratio], system_prompt=SYSTEM_PROMPT)
    agent(
        "A synthetic household has a $900,000 portfolio and wants to spend "
        "$50,000 a year in retirement. What is their funded ratio, and what "
        "does it mean?"
    )


if __name__ == "__main__":
    main()

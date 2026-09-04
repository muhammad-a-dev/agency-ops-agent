"""Optional CLI for running a single task offline."""

from __future__ import annotations

import argparse
import sys

from agency_ops_agent.agent import Agent
from agency_ops_agent.logging_config import configure_logging
from agency_ops_agent.settings import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agency-ops-agent",
        description="Run a single agency-ops agent task offline (no API server).",
    )
    parser.add_argument("task", help="Natural-language task for the agent")
    parser.add_argument(
        "--url",
        default=None,
        help="Optional URL to include in task context",
    )
    parser.add_argument(
        "--text",
        default=None,
        help="Optional text to summarize (context.text)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Override max agent steps",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print full AgentResult as JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    context: dict = {}
    if args.url:
        context["url"] = args.url
    if args.text:
        context["text"] = args.text

    agent = Agent(settings)
    result = agent.run(task=args.task, context=context, max_steps=args.max_steps)

    if args.as_json:
        print(result.model_dump_json(indent=2))
    else:
        print(result.answer)
        print(f"\n[steps={result.steps_used} mode={result.metadata.get('mode')}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Command-line interface for Rune."""

import argparse
import json
import os
import sys

from rich.console import Console
from rich.table import Table

from rune.harness.agent import Agent, AgentConfig
from rune.harness.store import SessionStore
from rune.agents import list_agents

console = Console()


def print_tool_call(name: str, args: dict, agent_name: str = "") -> None:
    """Print a tool call with Rich formatting."""
    prefix = f"[{agent_name}] " if agent_name else ""
    console.print(f"\n{prefix}[cyan bold]Tool:[/cyan bold] {name}")
    for key, value in args.items():
        if len(str(value)) > 100:
            value = str(value)[:100] + "..."
        console.print(f"  [dim]{key}:[/dim] {value}")


def print_tool_result(result, name: str) -> None:
    """Print a tool result with Rich formatting."""
    if result.success:
        console.print(f"[green]✓ {name} completed[/green]")
        if result.output:
            output = result.output
            if len(output) > 500:
                output = output[:500] + f"\n... ({len(result.output) - 500} more characters)"
            console.print(output)
    else:
        console.print(f"[red]✗ {name} failed: {result.error}[/red]")


def run_interactive(agent: Agent) -> None:
    """Run interactive mode.

    Interactive mode is implemented by the TUI (see rune/tui.py). This wrapper
    remains for backward compatibility with any external imports.
    """
    from rune.cli.tui import run_tui

    run_tui(agent)


def run_single(agent: Agent, prompt: str) -> None:
    """Run the agent with a single prompt."""
    try:
        for turn in agent.stream(prompt):
            for i, tool_call in enumerate(turn.tool_calls):
                args = json.loads(tool_call["function"]["arguments"])
                print_tool_call(tool_call["function"]["name"], args, turn.agent_name)
                if i < len(turn.tool_results):
                    print_tool_result(turn.tool_results[i], tool_call["function"]["name"])

            if turn.finished and turn.response:
                console.print(turn.response)
    finally:
        agent.shutdown()


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Rune - A coding agent with harness features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  rune                                             # Interactive build agent
  rune --agent plan                                # Interactive plan (read-only) agent
  rune -p "list all files"                         # Single prompt mode
  rune --mcp-config mcp.json                       # Load MCP tool servers
  rune --model openai/gpt-5.2-2025-12-11           # Use an OpenAI model
  rune --model anthropic/claude-sonnet-4-20250514  # Use an Anthropic model
""",
    )

    parser.add_argument("-p", "--prompt", help="Single prompt (non-interactive)")
    parser.add_argument(
        "--model",
        default="openai/gpt-5.2-2025-12-11",
        help="provider/model (default: openai/gpt-5.2-2025-12-11). "
             "Providers: openai, anthropic",
    )
    parser.add_argument("--agent", default="build", choices=["build", "plan"],
                        help="Agent type (default: build)")
    parser.add_argument("--mcp-config", default=None,
                        help="Path to MCP server config JSON file")
    parser.add_argument("--no-auto-approve", action="store_true",
                        help="Require confirmation for tool execution")
    parser.add_argument(
        "--ui",
        default="tui",
        choices=["tui"],
        help="Interactive UI mode (default: tui)",
    )
    parser.add_argument(
        "--resume",
        metavar="SESSION_ID",
        default=None,
        help="Resume an existing session by ID",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List recent sessions and exit",
    )

    args = parser.parse_args()

    # Handle --list-sessions: print table of recent sessions and exit
    if args.list_sessions:
        store = SessionStore()
        sessions = store.list_sessions()
        store.close()

        table = Table(title="Recent Sessions", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", max_width=40)
        table.add_column("Directory", max_width=30)
        table.add_column("Updated", no_wrap=True)
        table.add_column("Turns", justify="right")

        for s in sessions:
            table.add_row(
                s["session_id"],
                s["title"] or "[dim](no title)[/dim]",
                s["working_dir"],
                s["updated_at"],
                str(s["turn_count"]),
            )

        console.print(table)
        return

    # Resolve MCP config path
    mcp_path = args.mcp_config
    if mcp_path and not os.path.isabs(mcp_path):
        mcp_path = os.path.abspath(mcp_path)

    config = AgentConfig(
        model=args.model,
        agent_name=args.agent,
        auto_approve_tools=not args.no_auto_approve,
        mcp_config_path=mcp_path,
    )

    def approval_callback(tool_name: str, tool_id: str, arguments: dict) -> bool:
        console.print(f"\n[yellow]Tool request: {tool_name}[/yellow]")
        for key, value in arguments.items():
            console.print(f"  {key}: {value}")
        response = console.input("[yellow]Approve? [y/N][/yellow] ").strip().lower()
        return response in ("y", "yes")

    agent = Agent(
        config=config,
        approval_callback=approval_callback if not config.auto_approve_tools else None,
    )

    # Handle --resume: load existing session before running
    if args.resume:
        try:
            agent.resume_session(args.resume)
            console.print(f"[green]Resumed session {args.resume}[/green]")
        except KeyError:
            console.print(f"[red]Session {args.resume!r} not found.[/red]")
            sys.exit(1)

    if args.prompt:
        run_single(agent, args.prompt)
    else:
        from rune.cli.tui import run_tui

        run_tui(agent)


if __name__ == "__main__":
    main()

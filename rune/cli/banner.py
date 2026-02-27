"""Welcome banner, ASCII art, and sigil for the Rune CLI.

Pure display functions — no agent state modified here.
"""

from __future__ import annotations

from importlib.metadata import version as _pkg_version

try:
    VERSION = _pkg_version("rune-agent")
except Exception:
    VERSION = "0.2.0"


# ---------------------------------------------------------------------------
# ASCII art
# ---------------------------------------------------------------------------

# "RUNE" in full-block box-drawing letters, gold→bronze gradient top-to-bottom
RUNE_LOGO = """\
[bold #FFD700]██████╗ ██╗   ██╗███╗   ██╗███████╗[/]
[bold #FFD700]██╔══██╗██║   ██║████╗  ██║██╔════╝[/]
[#FFBF00]██████╔╝██║   ██║██╔██╗ ██║█████╗  [/]
[#FFBF00]██╔══██╗██║   ██║██║╚██╗██║██╔══╝  [/]
[#CD7F32]██║  ██║╚██████╔╝██║ ╚████║███████╗[/]
[#CD7F32]╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝[/]"""

# Vegvísir-inspired runic compass.
# Cardinal runes: ᚱ north · ᛖ east · ᚾ south · ᚢ west
RUNE_SIGIL = (
    "[bold #c8a84b]            ᚱ[/]\n"
    "[#CD7F32]            │[/]\n"
    "[#B8860B]      ╲     │     ╱[/]\n"
    "[#CD7F32]       ╲────┤────╱[/]\n"
    "[#FFBF00]       │╲   │   ╱│[/]\n"
    "[bold #c8a84b]ᚢ[/][#FFD700] ────╫──╲──┼──╱──╫──── [/][bold #c8a84b]ᛖ[/]\n"
    "[#FFBF00]       │╱   │   ╲│[/]\n"
    "[#CD7F32]       ╱────┤────╲[/]\n"
    "[#B8860B]      ╱     │     ╲[/]\n"
    "[#CD7F32]            │[/]\n"
    "[bold #c8a84b]            ᚾ[/]"
)


# ---------------------------------------------------------------------------
# Banner builder
# ---------------------------------------------------------------------------

def build_welcome_banner(console, agent) -> None:
    """Print the full startup banner to *console* (a ``rich.console.Console``).

    Called once before the prompt_toolkit TUI event loop starts, so the banner
    lives in the terminal's scrollback above the interactive interface.
    """
    from rich.panel import Panel
    from rich.table import Table

    tools = agent._get_permitted_tools()
    n_tools = len(tools)
    model = agent.config.model
    cwd = agent.session.working_dir
    session_id = agent.session.session_id
    agent_name = agent.agent_def.name

    model_short = model.split("/")[-1] if "/" in model else model
    if len(model_short) > 30:
        model_short = model_short[:27] + "…"

    # --- Big block logo ---
    console.print()
    console.print(RUNE_LOGO)
    console.print()

    # --- Left column: sigil + session summary ---
    left_lines = [
        "",
        RUNE_SIGIL,
        "",
        f"[#FFBF00]{agent_name}[/]  [dim #B8860B]{model_short}[/]",
        f"[dim #B8860B]{cwd}[/]",
        f"[dim #8B8682]session · {session_id}[/]",
    ]
    left_content = "\n".join(left_lines)

    # --- Right column: tool list ---
    _MAX_TOOLS = 20
    right_lines: list[str] = [
        f"[bold #FFBF00]Available Tools  ({n_tools})[/]",
        "",
    ]
    for t in tools[:_MAX_TOOLS]:
        fn = t["function"]
        name = fn["name"]
        desc = (fn.get("description") or "").split("\n")[0]
        if len(desc) > 44:
            desc = desc[:41] + "…"
        right_lines.append(
            f"[dim #B8860B]·[/] [#FFF8DC]{name}[/]  [dim #888888]{desc}[/]"
        )
    if n_tools > _MAX_TOOLS:
        right_lines.append(
            f"[dim #B8860B]  … and {n_tools - _MAX_TOOLS} more[/]"
        )
    right_lines += [
        "",
        f"[dim #B8860B]{n_tools} tools · type [/][dim #888888]/help[/][dim #B8860B] for commands[/]",
    ]
    right_content = "\n".join(right_lines)

    # --- Assemble panel ---
    layout = Table.grid(padding=(0, 3))
    layout.add_column("left", justify="left")
    layout.add_column("right", justify="left")
    layout.add_row(left_content, right_content)

    panel = Panel(
        layout,
        title=f"[bold #FFD700]ᚱᚢᚾᛖ  Rune Agent  v{VERSION}[/]",
        subtitle="[dim #B8860B]cast spells on your data[/]",
        border_style="#CD7F32",
        padding=(0, 1),
    )

    console.print(panel)
    console.print()

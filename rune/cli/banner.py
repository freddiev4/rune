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
# Rune armor colour palette  (cool steel-blue, lightest → darkest)
#
#   _C1  #b8d8e8  bright silver-blue   — top highlights / rune characters
#   _C2  #78a8c0  medium teal-blue     — mid-tone, inner sigil lines
#   _C3  #4a7896  main armour body     — dominant colour
#   _C4  #2e5068  shadow               — recessed areas
#   _C5  #1c3a50  deep shadow          — deepest recesses / outer edges
# ---------------------------------------------------------------------------

_C1 = "#b8d8e8"
_C2 = "#78a8c0"
_C3 = "#4a7896"
_C4 = "#2e5068"
_C5 = "#1c3a50"


# ---------------------------------------------------------------------------
# ASCII art
# ---------------------------------------------------------------------------

# "RUNE" in full-block box-drawing letters.
# Gradient bright (top) → dark (bottom), like light catching the armour.
RUNE_LOGO = (
    f"[bold {_C1}]██████╗ ██╗   ██╗███╗   ██╗███████╗[/]\n"
    f"[bold {_C1}]██╔══██╗██║   ██║████╗  ██║██╔════╝[/]\n"
    f"[{_C2}]██████╔╝██║   ██║██╔██╗ ██║█████╗  [/]\n"
    f"[{_C2}]██╔══██╗██║   ██║██║╚██╗██║██╔══╝  [/]\n"
    f"[{_C3}]██║  ██║╚██████╔╝██║ ╚████║███████╗[/]\n"
    f"[{_C3}]╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝[/]"
)

# Vegvísir-inspired runic compass.
# Cardinal runes: ᚱ north · ᛖ east · ᚾ south · ᚢ west
# Centre is brightest; arms darken toward the outer tips.
RUNE_SIGIL = (
    f"[bold {_C1}]            ᚱ[/]\n"
    f"[{_C3}]            │[/]\n"
    f"[{_C4}]      ╲     │     ╱[/]\n"
    f"[{_C3}]       ╲────┤────╱[/]\n"
    f"[{_C2}]       │╲   │   ╱│[/]\n"
    f"[bold {_C1}]ᚢ[/][{_C2}] ────╫──╲──┼──╱──╫──── [/][bold {_C1}]ᛖ[/]\n"
    f"[{_C2}]       │╱   │   ╲│[/]\n"
    f"[{_C3}]       ╱────┤────╲[/]\n"
    f"[{_C4}]      ╱     │     ╲[/]\n"
    f"[{_C3}]            │[/]\n"
    f"[bold {_C1}]            ᚾ[/]"
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
        f"[{_C1}]{agent_name}[/]  [dim {_C3}]{model_short}[/]",
        f"[dim {_C3}]{cwd}[/]",
        f"[dim {_C4}]session · {session_id}[/]",
    ]
    left_content = "\n".join(left_lines)

    # --- Right column: tool list ---
    _MAX_TOOLS = 20
    right_lines: list[str] = [
        f"[bold {_C2}]Available Tools  ({n_tools})[/]",
        "",
    ]
    for t in tools[:_MAX_TOOLS]:
        fn = t["function"]
        name = fn["name"]
        desc = (fn.get("description") or "").split("\n")[0]
        if len(desc) > 44:
            desc = desc[:41] + "…"
        right_lines.append(
            f"[dim {_C3}]·[/] [{_C1}]{name}[/]  [dim {_C4}]{desc}[/]"
        )
    if n_tools > _MAX_TOOLS:
        right_lines.append(f"[dim {_C3}]  … and {n_tools - _MAX_TOOLS} more[/]")
    right_lines += [
        "",
        f"[dim {_C3}]{n_tools} tools · type [/][{_C2}]/help[/][dim {_C3}] for commands[/]",
    ]
    right_content = "\n".join(right_lines)

    # --- Assemble panel ---
    layout = Table.grid(padding=(0, 3))
    layout.add_column("left", justify="left")
    layout.add_column("right", justify="left")
    layout.add_row(left_content, right_content)

    panel = Panel(
        layout,
        title=f"[bold {_C1}]ᚱᚢᚾᛖ  Rune Agent  v{VERSION}[/]",
        subtitle=f"[dim {_C3}]cast spells on your data[/]",
        border_style=_C3,
        padding=(0, 1),
    )

    console.print(panel)
    console.print()

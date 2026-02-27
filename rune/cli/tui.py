"""Persistent prompt_toolkit TUI for Rune.

This provides a two-pane interface:
- Scrollable output log (top)
- Fixed multiline input box (bottom)

Slash-command autocomplete, interrupt-and-redirect, and a richer set of
in-session commands are supported.
"""

from __future__ import annotations

import asyncio
import json
import random
import threading
from dataclasses import dataclass
from typing import Optional

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.bindings.basic import load_basic_bindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Float,
    FloatContainer,
    ScrollOffsets,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.margins import Margin
from prompt_toolkit.styles import Style
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.widgets import TextArea
from rune.agents import list_agents


_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# Runescape-themed action verbs for spinner status
_RUNE_VERBS = [
    "Smithing",
    "Mining",
    "Fishing",
    "Cooking",
    "Woodcutting",
    "Crafting",
    "Runecrafting",
    "Firemaking",
    "Fletching",
    "Brewing",
    "Slaying",
    "Training",
    "Grinding",
    "Questing",
    "Enchanting",
    "Alching",
    "Thieving",
    "Climbing",
    "Forging",
    "Smelting",
    "Casting",
    "Conjuring",
]

_SLASH_COMMANDS = sorted(
    [
        ("exit",    "Exit rune"),
        ("reset",   "Clear session history"),
        ("history", "Show conversation history"),
        ("status",  "Show session stats"),
        ("agents",  "List available agents"),
        ("switch",  "Switch agent: /switch <agent>"),
        ("retry",   "Re-run the last prompt"),
        ("undo",    "Remove last exchange from history"),
        ("model",   "Switch model: /model <provider/model>"),
        ("save",    "Save session to JSON: /save [filename]"),
        ("tools",   "List available tools"),
        ("compact", "Compact conversation history"),
    ],
    key=lambda x: x[0],
)

_INITIAL_HELP = (
    "Commands: /"
    + "  /".join(cmd for cmd, _ in _SLASH_COMMANDS)
    + "\n"
    "Ctrl+C: Interrupt agent  │  Ctrl+O: Toggle details  │  "
    "PgUp/PgDn: Scroll  │  Home/End: Jump  │  Ctrl+D: Exit"
)

# ASCII art banner — each letter column is separated so the lexer can
# detect "banner art" lines by the leading " |" pattern.
_RUNE_ART = [
    r" |\     |     | |\   | |=====",
    r" | \    |     | | \  | |     ",
    r" |--\   |     | |  \ | |==== ",
    r" |   \  |     | |   \| |     ",
    r" |    \ |_____| |    | |=====",
]


def _build_splash(agent) -> str:
    """Build the startup splash: runic ASCII art on the left, session info on the right."""
    n_tools = len(agent._get_permitted_tools())
    info = [
        " ᚱᚢᚾᛖ  runic agent framework",
        "",
        f" Agent:    {agent.agent_def.name}",
        f" Model:    {agent.config.model}",
        f" Session:  {agent.session.session_id}",
        f" Tools:    {n_tools} available",
    ]
    art_w = max(len(line) for line in _RUNE_ART)
    rows = max(len(_RUNE_ART), len(info))
    lines = []
    for i in range(rows):
        left = _RUNE_ART[i] if i < len(_RUNE_ART) else " " * art_w
        right = info[i] if i < len(info) else ""
        lines.append(f"{left:<{art_w}}{right}")
    lines.append("")
    lines.append(" " + "─" * (art_w + 30))
    lines.append(" Type / for commands  ·  Ctrl+C to interrupt  ·  Ctrl+D to exit")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slash-command completer
# ---------------------------------------------------------------------------

class _SlashCommandCompleter(Completer):
    """Show slash-command completions when the input starts with '/'."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        # Only complete on a single-line input that starts with /
        if "\n" in text or not text.startswith("/"):
            return
        
        word = text[1:]
        for cmd, desc in _SLASH_COMMANDS:
            if cmd.startswith(word):
                yield Completion(
                    cmd,
                    start_position=-len(word),
                    display=f"/{cmd}",
                    display_meta=desc,
                )


# ---------------------------------------------------------------------------
# Output lexer
# ---------------------------------------------------------------------------

from prompt_toolkit.lexers import Lexer


class _OutputPTKLexer(Lexer):
    """Render-time styling for the output buffer.

    Any line that starts with '> ' is styled as echoed user input.
    Text wrapped in backticks is styled as inline code.
    """

    def lex_document(self, document):  # type: ignore[override]
        def get_line(lineno: int):
            try:
                line = document.lines[lineno]
            except Exception:
                return []

            if line.startswith("> "):
                return [("class:user_input", line)]

            # ASCII art banner lines (contain runic stroke characters)
            if line.startswith(" |") and any(c in line for c in r"\/_="):
                return [("class:banner_art", line)]

            # Lines containing Elder Futhark rune characters — gold-tint the runes,
            # leave the surrounding text normal.
            _RUNES = "ᚱᚢᚾᛖᚠᚨᚦᚹᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ"
            if any(c in line for c in _RUNES):
                parts: list = []
                for ch in line:
                    if ch in _RUNES:
                        parts.append(("class:runes", ch))
                    else:
                        parts.append(("", ch))
                return parts

            fragments: list = []
            pos = 0
            while pos < len(line):
                tick_start = line.find("`", pos)
                if tick_start == -1:
                    if pos < len(line):
                        fragments.append(("", line[pos:]))
                    break
                if tick_start > pos:
                    fragments.append(("", line[pos:tick_start]))
                tick_end = line.find("`", tick_start + 1)
                if tick_end == -1:
                    fragments.append(("", line[tick_start:]))
                    break
                code_content = line[tick_start + 1:tick_end]
                fragments.append(("class:code", code_content))
                pos = tick_end + 1

            return fragments if fragments else [("", line)]

        return get_line


# ---------------------------------------------------------------------------
# Prompt margin
# ---------------------------------------------------------------------------

class _PromptGlyphMargin(Margin):
    """Left margin that shows a prompt glyph only on the first visible line."""

    def __init__(self, prompt="❯ ") -> None:
        self._prompt = prompt

    @property
    def prompt(self) -> str:
        p = self._prompt
        return p() if callable(p) else p

    def get_width(self, get_ui_content) -> int:  # type: ignore[override]
        return len(self.prompt)

    def create_margin(self, window_render_info, width: int, height: int):  # type: ignore[override]
        fragments = [("class:prompt", self.prompt + "\n")]
        pad = " " * len(self.prompt)
        fragments.extend([("class:prompt", pad + "\n") for _ in range(max(0, height - 1))])
        return fragments


# ---------------------------------------------------------------------------
# Printer helper
# ---------------------------------------------------------------------------

@dataclass
class TuiPrinter:
    """Appends text into the output TextArea."""

    output: TextArea
    app: Application
    follow_mode: dict[str, bool]

    def print(self, text: str = "") -> None:
        buf = self.output.buffer
        buf.insert_text(text + "\n", move_cursor=True)
        self.output.buffer.cursor_position = len(self.output.text)
        try:
            self.output.window.vertical_scroll = 10**9  # type: ignore[attr-defined]
        except Exception:
            pass
        if self.follow_mode.get("enabled", True):
            try:
                self.output.control.move_cursor_to_end()
            except Exception:
                pass
        self.app.invalidate()

    def print_fragments(self, fragments) -> None:
        from prompt_toolkit.formatted_text import fragment_list_to_text
        self.print(fragment_list_to_text(fragments))


# ---------------------------------------------------------------------------
# Main TUI entry point
# ---------------------------------------------------------------------------

def run_tui(agent) -> None:
    """Run Rune in a persistent TUI."""

    style = Style.from_dict(
        {
            "frame.border": "#b0b0b0",
            "title": "bold #b0b0b0",
            "prompt": "#b0b0b0",
            "status": "#b0b0b0",
            "user_input": "bg:#ffffff fg:#000000",
            "code": "#5b9bd5",
            "spinner": "#b0b0b0",
            "completion-menu": "bg:#1a1a1a #e8e8e8",
            "completion-menu.completion": "bg:#1a1a1a #e8e8e8",
            "completion-menu.completion.current": "bg:#005faf #ffffff bold",
            "completion-menu.meta.completion": "bg:#2d2d2d #707070",
            "completion-menu.meta.completion.current": "bg:#004d8f #aaccee",
            "scrollbar.background": "bg:#3a3a3a",
            "scrollbar.button": "bg:#888888",
            "banner_art": "#505050",
            "runes": "bold #c8a84b",
        }
    )

    kb = KeyBindings()

    # ------------------------------------------------------------------
    # Shared state
    # ------------------------------------------------------------------
    tui_state: dict = {"last_prompt": None}
    _cancel_event = threading.Event()

    # ------------------------------------------------------------------
    # Output area
    # ------------------------------------------------------------------
    output_buffer = Buffer()
    output_control = BufferControl(
        buffer=output_buffer,
        lexer=_OutputPTKLexer(),
        focusable=True,
    )
    output_window = Window(
        content=output_control,
        wrap_lines=True,
        always_hide_cursor=True,
        scroll_offsets=ScrollOffsets(top=1, bottom=1),
    )

    # Lightweight TextArea wrapper for existing code paths
    output = TextArea(text="", focusable=True)
    output.buffer = output_buffer  # type: ignore[attr-defined]
    output.control = output_control  # type: ignore[attr-defined]

    follow_mode: dict[str, bool] = {"enabled": True}
    show_details: dict[str, bool] = {"enabled": False}
    details_readonly: dict[str, bool] = {"enabled": True}

    # ------------------------------------------------------------------
    # Details pane
    # ------------------------------------------------------------------
    details_buffer = Buffer(read_only=Condition(lambda: details_readonly["enabled"]))
    details_control = BufferControl(
        buffer=details_buffer,
        focusable=True,
        focus_on_click=True,
    )
    details_window = Window(
        content=details_control,
        wrap_lines=True,
        scroll_offsets=ScrollOffsets(top=1, bottom=1),
    )

    # ------------------------------------------------------------------
    # Input area with slash-command autocomplete
    # ------------------------------------------------------------------
    input_buffer = Buffer(
        multiline=True,
        completer=_SlashCommandCompleter(),
        complete_while_typing=True,
    )

    def _prompt_char() -> str:
        return {"build": "#", "plan": "?"}.get(agent.agent_def.name, ">")

    def _prompt_title() -> str:
        return f"{agent.agent_def.name} {_prompt_char()}"

    input_control = BufferControl(buffer=input_buffer)
    input_window = Window(
        content=input_control,
        height=1,
        wrap_lines=False,
        left_margins=[_PromptGlyphMargin(lambda: f"{_prompt_char()} ")],
    )

    header = FormattedTextControl(
        text=lambda: [
            ("class:title", "Rune"),
            ("", "  "),
            ("class:status", f"Agent: {agent.agent_def.name}  Model: {agent.config.model}"),
        ]
    )

    # ------------------------------------------------------------------
    # Spinner
    # ------------------------------------------------------------------
    spinner: dict[str, object] = {
        "active": False,
        "i": 0,
        "task": None,
        "line": "",
        "status": random.choice(_RUNE_VERBS) + "…",
        "verb": random.choice(_RUNE_VERBS),
    }

    def _spinner_text():
        if not spinner.get("active"):
            return []
        status = str(spinner.get("status") or "Working…")
        if not show_details["enabled"] and details_buffer.text.strip():
            status += " (Ctrl+O for details)"
        frame = _SPINNER_FRAMES[int(spinner.get("i", 0)) % len(_SPINNER_FRAMES)]
        return [("class:spinner", f"{frame} {status}")]

    spinner_status = FormattedTextControl(text=_spinner_text)

    def _set_spinner_status(status: str) -> None:
        spinner["status"] = status or (spinner.get("verb", "Working") + "…")

    def _start_spinner() -> None:
        if spinner.get("active"):
            return
        spinner["active"] = True
        spinner["i"] = int(spinner.get("i", 0))
        spinner["verb"] = random.choice(_RUNE_VERBS)
        spinner["status"] = spinner["verb"] + "…"
        try:
            app.invalidate()
        except Exception:
            pass

    def _stop_spinner() -> None:
        if not spinner.get("active"):
            return
        spinner["active"] = False
        spinner["i"] = 0
        try:
            app.invalidate()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Turn rendering
    # ------------------------------------------------------------------
    printer_holder: dict[str, Optional[TuiPrinter]] = {"p": None}

    def _append_agent_turn(turn) -> None:
        p = printer_holder["p"]
        if p is None:
            return

        details_readonly["enabled"] = False

        for i, tool_call in enumerate(turn.tool_calls):
            try:
                args = json.loads(tool_call["function"]["arguments"])
            except Exception:
                args = {"arguments": tool_call["function"].get("arguments")}
            tool_name = tool_call["function"]["name"]
            _set_spinner_status(f"Tool: {tool_name}")

            summary_arg = None
            if "command" in args:
                summary_arg = args["command"]
            elif "file_path" in args:
                summary_arg = args["file_path"]
            elif "pattern" in args:
                summary_arg = args["pattern"]
            elif "prompt" in args:
                raw = str(args.get("prompt", ""))
                summary_arg = raw[:50] + "..." if len(raw) > 50 else raw

            if summary_arg:
                p.print(f"⏺ {tool_name}({summary_arg})")
            else:
                p.print(f"⏺ {tool_name}")

            details_buffer.insert_text(f"[{turn.agent_name}] Tool: {tool_name}\n")
            for k, v in (args or {}).items():
                details_buffer.insert_text(f"  {k}: {v}\n")

            if i < len(turn.tool_results):
                tr = turn.tool_results[i]
                if tr.success:
                    _set_spinner_status(f"Tool: {tool_name} ✓")
                    if tr.output:
                        output_preview = str(tr.output).strip()
                        if len(output_preview) > 100:
                            output_preview = "(Content available in details - Ctrl+O)"
                        elif not output_preview:
                            output_preview = "(No content)"
                        p.print(f"  ⎿ {output_preview}")
                    else:
                        p.print("  ⎿ (No content)")
                    details_buffer.insert_text(f"  ✓ {tool_name} completed\n")
                    if tr.output:
                        details_buffer.insert_text(f"{tr.output}\n")
                else:
                    _set_spinner_status(f"Tool: {tool_name} ✗")
                    p.print(f"  ⎿ Error: {tr.error}")
                    details_buffer.insert_text(f"  ✗ {tool_name} failed: {tr.error}\n")

            p.print("")
            details_buffer.insert_text("\n")

        details_readonly["enabled"] = True

        if turn.finished and turn.response:
            _stop_spinner()
            _set_spinner_status("Working…")
            p.print(f"⏺ {turn.response}")

    # ------------------------------------------------------------------
    # Agent runner (supports cancellation via _cancel_event)
    # ------------------------------------------------------------------
    def _schedule_agent_run(prompt: str) -> None:
        async def _run_agent() -> None:
            _cancel_event.clear()

            # Clear previous details
            details_readonly["enabled"] = False
            details_buffer.text = ""
            details_readonly["enabled"] = True

            _start_spinner()
            await asyncio.sleep(0.05)

            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _process_agent_stream, prompt)
            except Exception as e:
                p = printer_holder["p"]
                if p:
                    p.print(f"Error: {e}")
            finally:
                _stop_spinner()

        def _process_agent_stream(p: str) -> None:
            try:
                for turn in agent.stream(p):
                    if _cancel_event.is_set():
                        break
                    _append_agent_turn(turn)
            finally:
                _cancel_event.clear()

        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(_run_agent())
        except Exception:
            # Fallback synchronous path
            _start_spinner()
            try:
                _process_agent_stream(prompt)
            except Exception as e:
                pr = printer_holder["p"]
                if pr:
                    pr.print(f"Error: {e}")
            finally:
                _stop_spinner()

    # ------------------------------------------------------------------
    # Slash command handler
    # ------------------------------------------------------------------
    def _handle_slash_command(cmdline: str) -> None:
        """Handle a slash command (cmdline is the text after the leading '/')."""
        _stop_spinner()
        if not cmdline:
            p = printer_holder["p"]
            if p:
                p.print(_INITIAL_HELP)
            return

        cmd, *rest = cmdline.split(None, 1)
        arg = rest[0] if rest else ""
        p = printer_holder["p"]

        if cmd in {"exit"}:
            app.exit(result=None)

        elif cmd == "reset":
            agent.reset()
            if p:
                p.print("Session reset.")

        elif cmd == "history":
            if p:
                for msg in agent.session.messages:
                    content = (msg.content or "").replace("\n", " ")
                    if len(content) > 200:
                        content = content[:200] + "..."
                    p.print(f"{msg.role}: {content}")

        elif cmd == "status":
            s = agent.session
            if p:
                p.print(f"Session:     {s.session_id}")
                p.print(f"Turns:       {s.turn_count}")
                p.print(f"Messages:    {len(s.messages)}")
                p.print(
                    f"Tokens:      {s.usage.total_tokens} "
                    f"(prompt: {s.usage.prompt_tokens}, "
                    f"completion: {s.usage.completion_tokens})"
                )
                p.print(f"Model:       {agent.config.model}")
                p.print(f"Working dir: {s.working_dir}")

        elif cmd == "agents":
            if p:
                p.print("Available agents:")
                for ag in list_agents():
                    marker = " ←" if ag.name == agent.agent_def.name else ""
                    p.print(f"  {ag.name}{marker}: {ag.description}")

        elif cmd == "switch":
            if not arg:
                if p:
                    p.print("Usage: /switch <agent>")
                return
            try:
                agent.switch_agent(arg.strip())
                if p:
                    p.print(f"Switched to {arg.strip()} agent.")
            except ValueError as e:
                if p:
                    p.print(str(e))

        elif cmd == "retry":
            last = tui_state.get("last_prompt")
            if not last:
                if p:
                    p.print("Nothing to retry.")
                return
            agent.session.undo_last_exchange()
            if p:
                p.print(f"> {last}  [retry]")
                p.print("")
            _schedule_agent_run(last)

        elif cmd == "undo":
            if agent.session.undo_last_exchange():
                if p:
                    p.print("Last exchange removed from history.")
            else:
                if p:
                    p.print("Nothing to undo.")

        elif cmd == "model":
            if not arg:
                if p:
                    p.print(f"Current model: {agent.config.model}")
                    p.print("Usage: /model <provider/model>")
                    p.print("  e.g. /model anthropic/claude-sonnet-4-20250514")
                    p.print("       /model openai/gpt-4o")
                return
            try:
                agent.switch_model(arg.strip())
                if p:
                    p.print(f"Model switched to {arg.strip()}")
            except (ValueError, ImportError) as e:
                if p:
                    p.print(f"Error: {e}")

        elif cmd == "save":
            filename = arg.strip() or f"rune-{agent.session.session_id}.json"
            try:
                agent.session.save(filename)
                if p:
                    p.print(f"Session saved to {filename}")
            except Exception as e:
                if p:
                    p.print(f"Save failed: {e}")

        elif cmd == "tools":
            tools = agent._get_permitted_tools()
            if p:
                p.print(f"Available tools ({len(tools)}):")
                for t in tools:
                    fn = t["function"]
                    desc = fn.get("description", "")
                    if len(desc) > 60:
                        desc = desc[:60] + "…"
                    p.print(f"  {fn['name']}: {desc}")

        elif cmd == "compact":
            try:
                agent._compact_session()
                if p:
                    p.print("Session compacted.")
            except Exception as e:
                if p:
                    p.print(f"Compact failed: {e}")

        else:
            if p:
                p.print(f"Unknown command: /{cmd}")
                p.print("Type / to see available commands.")

    # ------------------------------------------------------------------
    # Submit handler
    # ------------------------------------------------------------------
    def _submit() -> None:
        text = input_buffer.text.strip()
        if not text:
            return

        p = printer_holder["p"]

        # Clear input immediately so the UI feels responsive
        input_buffer.text = ""
        try:
            app.invalidate()
        except Exception:
            pass

        # Echo input (slash commands and regular messages alike)
        if p:
            p.print(f"> {text}")
            p.print("")

        if text.startswith("/"):
            _handle_slash_command(text[1:].strip())
            return

        # Guard against bare command words without a leading slash
        if text in {"exit", "reset", "history", "agents", "status", "retry",
                    "undo", "tools", "compact"} or text.startswith("switch "):
            if p:
                p.print("Commands must start with '/'.")
            return

        tui_state["last_prompt"] = text
        _schedule_agent_run(text)

    # ------------------------------------------------------------------
    # Key bindings
    # ------------------------------------------------------------------
    @kb.add("enter", filter=Condition(lambda: True))
    def _(event) -> None:
        buf = event.app.current_buffer
        # If a completion is highlighted, accept it instead of submitting
        if buf.complete_state and buf.complete_state.current_completion:
            buf.apply_completion(buf.complete_state.current_completion)
            return
        doc = buf.document
        if doc.is_cursor_at_the_end:
            _submit()
        else:
            buf.insert_text("\n")

    @kb.add("s-tab")
    def _(event) -> None:
        event.app.current_buffer.insert_text("\n")

    @kb.add("c-o")
    def _(event) -> None:
        show_details["enabled"] = not show_details["enabled"]
        if show_details["enabled"]:
            try:
                event.app.layout.focus(details_window)
            except Exception:
                pass
        else:
            try:
                event.app.layout.focus(input_window)
            except Exception:
                pass
        try:
            event.app.invalidate()
        except Exception:
            pass

    @kb.add("c-c")
    def _(event) -> None:
        if spinner.get("active"):
            # Interrupt the running agent; stay in the TUI
            _cancel_event.set()
            p = printer_holder["p"]
            if p:
                p.print("[Interrupted — type a new message or /exit to quit]")
            try:
                event.app.layout.focus(input_window)
            except Exception:
                pass
        else:
            event.app.exit(result=None)

    @kb.add("c-d")
    def _(event) -> None:
        event.app.exit(result=None)

    # Scrolling — details pane when visible, output pane otherwise
    @kb.add("pageup")
    def _(event) -> None:
        target = details_buffer if show_details["enabled"] else output_buffer
        if not show_details["enabled"]:
            follow_mode["enabled"] = False
        try:
            for _ in range(10):
                up = target.document.get_cursor_up_position()
                if up:
                    target.cursor_position = max(0, target.cursor_position + up)
                else:
                    break
            event.app.invalidate()
        except Exception:
            pass

    @kb.add("pagedown")
    def _(event) -> None:
        target = details_buffer if show_details["enabled"] else output_buffer
        try:
            for _ in range(10):
                down = target.document.get_cursor_down_position()
                if down:
                    target.cursor_position = min(
                        len(target.text), target.cursor_position + down
                    )
                else:
                    break
            event.app.invalidate()
        except Exception:
            pass

    @kb.add("home")
    def _(event) -> None:
        target = details_buffer if show_details["enabled"] else output_buffer
        if not show_details["enabled"]:
            follow_mode["enabled"] = False
        try:
            target.cursor_position = 0
            event.app.invalidate()
        except Exception:
            pass

    @kb.add("end", filter=Condition(lambda: show_details["enabled"]))
    def _(event) -> None:
        try:
            details_buffer.cursor_position = len(details_buffer.text)
            event.app.invalidate()
        except Exception:
            pass

    @kb.add("end", filter=Condition(lambda: not show_details["enabled"]))
    def _(event) -> None:
        follow_mode["enabled"] = True
        event.app.layout.focus(input_window)
        try:
            output.control.move_cursor_to_end()
        except Exception:
            pass
        event.app.invalidate()

    @kb.add("up", filter=Condition(lambda: show_details["enabled"]))
    def _(event) -> None:
        try:
            up = details_buffer.document.get_cursor_up_position()
            if up:
                details_buffer.cursor_position = max(0, details_buffer.cursor_position + up)
            event.app.invalidate()
        except Exception:
            pass

    @kb.add("down", filter=Condition(lambda: show_details["enabled"]))
    def _(event) -> None:
        try:
            down = details_buffer.document.get_cursor_down_position()
            if down:
                details_buffer.cursor_position = min(
                    len(details_buffer.text),
                    details_buffer.cursor_position + down,
                )
            event.app.invalidate()
        except Exception:
            pass

    all_bindings = merge_key_bindings([load_basic_bindings(), kb])

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    details_pane = ConditionalContainer(
        HSplit([
            Window(
                FormattedTextControl(
                    lambda: [("class:title",
                              "Tool Details (Ctrl+O to hide, ↑↓/PgUp/PgDn to scroll, Home/End to jump)")]
                ),
                height=1,
            ),
            Window(height=1, char="─", style="class:frame.border"),
            details_window,
            Window(height=1, char="─", style="class:frame.border"),
        ]),
        filter=Condition(lambda: show_details["enabled"]),
    )

    output_container = ConditionalContainer(
        output_window,
        filter=Condition(lambda: not show_details["enabled"]),
    )

    spinner_container = ConditionalContainer(
        HSplit([
            Window(FormattedTextControl(text=_spinner_text), height=1),
            Window(height=1),
        ]),
        filter=Condition(lambda: spinner.get("active", False)),
    )

    inner_root = HSplit([
        Window(header, height=1),
        output_container,
        details_pane,
        spinner_container,
        Window(height=1, char="─", style="class:frame.border"),
        Window(
            FormattedTextControl(lambda: [("class:prompt", _prompt_title())]),
            height=1,
        ),
        input_window,
        Window(height=1, char="─", style="class:frame.border"),
    ])

    # Wrap in FloatContainer so the completions menu can float above the layout
    root = FloatContainer(
        content=inner_root,
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(max_height=8, scroll_offset=1),
            ),
        ],
    )

    layout = Layout(root, focused_element=input_window)

    app: Application

    app = Application(
        layout=layout,
        key_bindings=all_bindings,
        style=style,
        full_screen=False,
        mouse_support=True,
    )
    printer_holder["p"] = TuiPrinter(output=output, app=app, follow_mode=follow_mode)

    # ------------------------------------------------------------------
    # Event loop
    # ------------------------------------------------------------------
    async def _run() -> None:
        async def _spinner_loop() -> None:
            while True:
                await asyncio.sleep(0.1)
                if spinner.get("active"):
                    spinner["i"] = int(spinner.get("i", 0)) + 1
                    try:
                        app.invalidate()
                    except Exception:
                        pass

        app_task = asyncio.create_task(app.run_async())
        spinner_task = asyncio.create_task(_spinner_loop())
        spinner["task"] = spinner_task

        printer_holder["p"].print(_build_splash(agent))
        try:
            await app_task
        finally:
            spinner_task.cancel()
            try:
                await spinner_task
            except Exception:
                pass
            if not app_task.done():
                app.exit(result=None)
                await app_task

    try:
        asyncio.run(_run())
    finally:
        agent.shutdown()

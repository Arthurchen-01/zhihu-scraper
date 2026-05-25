"""
widgets.py - Reusable home screen widgets for the interactive TUI.
"""

from rich.align import Align
from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.events import Key
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Footer, Static, TextArea
from textual.widgets._footer import FooterKey

from core.i18n import t


class InputCard(Widget):
    """Input surface for pasting Zhihu links into the TUI."""

    def __init__(self) -> None:
        super().__init__(id="input-card")

    def compose(self) -> ComposeResult:
        from core.i18n import t
        yield Static(t("input.label"), classes="section-label")
        yield ArchiveInput(
            placeholder=t("input.placeholder"),
            id="url-input",
        )
        yield Static(t("input.caption"), classes="section-caption")


class ArchiveInput(TextArea):
    """Multiline-safe input surface that still submits on Enter."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("soft_wrap", True)
        kwargs.setdefault("highlight_cursor_line", False)
        super().__init__(**kwargs)
        self.show_line_numbers = False

    class Submitted(Message):
        """Posted when the archive input should be parsed as a draft."""

        def __init__(self, input_widget: "ArchiveInput", value: str) -> None:
            super().__init__()
            self.input = input_widget
            self.value = value

    def on_key(self, event: Key) -> None:
        """Treat Enter as draft submission while preserving pasted multiline text."""
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self, self.text))
            return

        if event.key == "ctrl+r":
            event.prevent_default()
            event.stop()
            self.app.action_run_current_draft()
            return

        if event.key == "ctrl+y":
            event.prevent_default()
            event.stop()
            self.app.action_load_retry_draft()


class StatusPill(Widget):
    """Small render-only status label used by tests and compact diagnostics."""

    def __init__(self, label: str, value: str, tone: str) -> None:
        super().__init__()
        self._label = label
        self._value = value
        self._tone = tone

    def render(self) -> Group:
        tone_color = {
            "success": "#30d158",
            "warn": "#ffd60a",
            "danger": "#ff453a",
            "accent": "#0a84ff",
        }.get(self._tone, "#8e8e93")
        return Group(
            Align.center(Text(self._label, style="#8e8e93")),
            Align.center(Text(self._value, style=f"bold {tone_color}")),
        )


class MutableCard(Widget):
    """Shared mutable card for summary, queue, and recent-result panels."""

    _TONES = ("muted", "accent", "success", "warn", "danger")

    def __init__(self, card_id: str, title: str, lines: tuple[str, ...], tone: str) -> None:
        super().__init__(id=card_id)
        self._title = title
        self._lines = lines
        self._tone = tone

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal
        yield Horizontal(
            Static(self._get_indicator(self._tone), classes="card-indicator"),
            Static(self._title, classes="card-title"),
            classes="card-header-flow"
        )
        yield Static(self._format_lines(self._lines), classes="card-body")

    def on_mount(self) -> None:
        """Apply the initial tone class."""
        self._sync_tone()

    def update_content(self, title: str, lines: tuple[str, ...], tone: str) -> None:
        """Update the summary body after the app parses new input."""
        self._title = title
        self._lines = lines
        self._tone = tone
        self.query_one(".card-indicator", Static).update(self._get_indicator(tone))
        self.query_one(".card-title", Static).update(title)
        self.query_one(".card-body", Static).update(self._format_lines(lines))
        self._sync_tone()

    def _sync_tone(self) -> None:
        for candidate in self._TONES:
            self.set_class(candidate == self._tone, f"tone-{candidate}")

    def _get_indicator(self, tone: str) -> str:
        return {
            "success": "●",
            "warn": "●",
            "danger": "●",
            "accent": "●",
            "muted": "○",
        }.get(tone, "○")

    @staticmethod
    def _format_lines(lines: tuple[str, ...]) -> str:
        return "\n".join(f"• {line}" for line in lines)


class SummaryCard(MutableCard):
    """Mutable card that reflects the current parsed draft."""

    def __init__(self, title: str, lines: tuple[str, ...], tone: str) -> None:
        super().__init__("draft-card", title, lines, tone)


class QueueCard(MutableCard):
    """Mutable card that shows the current draft queue."""

    def __init__(self, title: str, lines: tuple[str, ...], tone: str) -> None:
        super().__init__("queue-card", title, lines, tone)


class HistoryCard(MutableCard):
    """Mutable card that shows recent execution results."""

    def __init__(self, title: str, lines: tuple[str, ...], tone: str) -> None:
        super().__init__("history-card", title, lines, tone)


class DetailCard(MutableCard):
    """Mutable card that shows detailed draft or execution information."""

    def __init__(self, title: str, lines: tuple[str, ...], tone: str) -> None:
        super().__init__("detail-card", title, lines, tone)


class LocalizedFooter(Footer):
    """Footer that translates binding descriptions using the active i18n locale.

    All binding descriptions are treated as i18n keys.
    To add a new language, simply add the key to the corresponding locale JSON.
    To add a new binding, define it in ZhihuInteractiveShell.BINDINGS with the
    i18n key as the description — no changes needed here.
    """

    def compose(self) -> ComposeResult:
        if not self._bindings_ready:
            return

        from collections import defaultdict
        from itertools import groupby

        active_bindings = self.screen.active_bindings
        bindings = [
            (binding, enabled, tooltip)
            for (_, binding, enabled, tooltip) in active_bindings.values()
            if binding.show
        ]

        action_to_bindings: defaultdict = defaultdict(list)
        for binding, enabled, tooltip in bindings:
            action_to_bindings[binding.action].append((binding, enabled, tooltip))

        self.styles.grid_size_columns = len(action_to_bindings)

        for _group, multi_bindings_iterable in groupby(
            action_to_bindings.values(),
            lambda multi_bindings_: multi_bindings_[0][0].group,
        ):
            multi_bindings = list(multi_bindings_iterable)
            for multi_binding_entry in multi_bindings:
                binding, enabled, tooltip = multi_binding_entry[0]
                # Translate description via i18n; fallback to original if key not found
                description = t(binding.description) if binding.description else ""
                yield FooterKey(
                    binding.key,
                    self.app.get_key_display(binding),
                    description,
                    binding.action,
                    disabled=not enabled,
                    tooltip=tooltip or description,
                ).data_bind(compact=Footer.compact)

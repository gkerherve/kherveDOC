"""AI Assistant dock — chat with an LLM that can write into the document.

The assistant talks to any provider in ai_providers.py. When you ask it
to write, it replies with a fenced ``latex`` block which this module
imports and inserts at the cursor as real, editable content (sections,
paragraphs, math, lists, tables…), exactly as if you had typed it.

The panel is a hideable side dock — the same hchat side-window pattern
used across the Kherve family. It runs on the standard library only
(providers use urllib); qtawesome icons are used when present and fall
back to text labels otherwise, so there is no hard new dependency.
"""
from __future__ import annotations

import json
import re

from PySide6.QtCore import QSettings, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDockWidget, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QSizePolicy, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

from . import ai_providers as providers
from .importers import import_body_fragment

_SETTINGS = ("kherveDOC", "kherveDOC")

try:                                    # optional — nicer icons when present
    import qtawesome as _qta
except Exception:                       # pragma: no cover - optional dep
    _qta = None


def _icon(glyph):
    """A qtawesome icon, or None when qtawesome isn't installed (the button
    then shows its text fallback instead)."""
    if _qta is None:
        return None
    try:
        return _qta.icon(glyph)
    except Exception:                   # pragma: no cover - bad glyph name
        return None


SYSTEM_PROMPT = r"""You are a writing assistant embedded in kherveDOC, a \
WYSIWYG LaTeX document editor. Help the user draft and edit their document.

The document class is "{docclass}". The document currently contains: \
{summary}.

When the user asks you to write, add, insert, draft or continue content, \
reply with one short sentence of plain prose and then a single fenced code \
block tagged latex holding ONLY document BODY LaTeX to insert. Do NOT \
output a code block unless the user actually wants content written into the \
document — answer questions with plain prose only.

Rules for the latex block:
- BODY ONLY. Never emit \documentclass, \usepackage, \begin{document} or \
\end{document} — the document already has a preamble.
- Use \section{...}, \subsection{...} for headings; blank lines separate \
paragraphs.
- Inline maths uses $...$; display maths uses \[ ... \] or \
\begin{equation}...\end{equation}.
- Lists use \begin{itemize}/\begin{enumerate} with \item.
- Tables use \begin{tabular}; figures use \begin{figure}.
- Emphasis: \textbf{...}, \textit{...}, \emph{...}.
- Keep it clean, compilable LaTeX. Do not wrap the whole answer in the \
code block — the prose sentence stays outside it."""


# ---------------------------------------------------------------- parsing
_FENCE_RE = re.compile(r"```(?:la?tex|tex)?\s*(.*?)```", re.DOTALL)


def prose_only(reply: str) -> str:
    """The human-readable part of a reply, with any LaTeX code removed.

    Cuts at the first code fence so a *truncated* block (no closing ```)
    still doesn't leak raw LaTeX into the chat transcript."""
    fence = reply.find("```")
    return (reply[:fence] if fence != -1 else reply).strip()


def extract_latex(reply: str) -> str:
    """Concatenate every fenced latex/tex block in *reply* (blank if none)."""
    blocks = [m.group(1).strip() for m in _FENCE_RE.finditer(reply)]
    return "\n\n".join(b for b in blocks if b)


def document_summary(doc) -> str:
    """A short description of the current document for the system prompt."""
    if doc is None or not doc.children:
        return "nothing yet (an empty document)"
    from .model import Section, Title
    titles = []
    for block in doc.children:
        if isinstance(block, Title):
            txt = _plain_text(block.children)
            if txt:
                titles.append(f"title “{txt}”")
        elif isinstance(block, Section):
            txt = _plain_text(block.children)
            if txt:
                titles.append(f"section “{txt}”")
    n = len(doc.children)
    head = ", ".join(titles[:8]) if titles else "no headings yet"
    return f"{n} block(s); {head}"


def _plain_text(inlines) -> str:
    from .model import Text
    return "".join(i.text for i in inlines if isinstance(i, Text)).strip()


# ---------------------------------------------------------------- worker
class _Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as exc:              # pragma: no cover - network
            self.failed.emit(str(exc))


# ---------------------------------------------------------------- settings
class AiSettingsDialog(QDialog):
    """Provider / model / API-key settings, like the rest of the family."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Chat Settings")
        self.setMinimumWidth(440)
        self._settings = QSettings(*_SETTINGS)
        self._worker = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.provider_combo = QComboBox()
        for key in providers.PROVIDERS:
            self.provider_combo.addItem(providers.DISPLAY_NAMES[key], key)
        form.addRow("Provider:", self.provider_combo)

        model_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.refresh_btn = QToolButton()
        self._set_btn(self.refresh_btn, "mdi.refresh", "↻")
        self.refresh_btn.setToolTip("Refresh the model list from the provider")
        model_row.addWidget(self.model_combo, 1)
        model_row.addWidget(self.refresh_btn)
        form.addRow("Model:", model_row)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self.key_edit)

        self.base_label = QLabel("Base URL:")
        self.base_edit = QLineEdit()
        form.addRow(self.base_label, self.base_edit)

        self.help_box = QGroupBox("How to get an API key")
        help_layout = QVBoxLayout(self.help_box)
        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        help_layout.addWidget(self.help_label)
        layout.addWidget(self.help_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.provider_combo.currentIndexChanged.connect(self._load_provider)
        self.refresh_btn.clicked.connect(self._refresh)

        saved = self._settings.value("ai/provider", "Claude")
        idx = self.provider_combo.findData(saved)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self._load_provider()

    @staticmethod
    def _set_btn(btn, glyph, fallback):
        ico = _icon(glyph)
        if ico is not None:
            btn.setIcon(ico)
        else:
            btn.setText(fallback)

    def _provider(self):
        return self.provider_combo.currentData()

    def _load_provider(self, *_):
        provider = self._provider()
        self.key_edit.setText(self._settings.value(f"ai/key/{provider}", ""))
        self.base_edit.setText(self._settings.value(f"ai/base/{provider}", ""))
        self.key_edit.setEnabled(provider in providers.NEEDS_KEY)
        show_base = provider in ("Local", "Ollama")
        self.base_label.setVisible(show_base)
        self.base_edit.setVisible(show_base)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(providers.DEFAULT_MODELS.get(provider, []))
        saved = self._settings.value(f"ai/model/{provider}", "")
        if saved:
            self.model_combo.setCurrentText(saved)
        self.model_combo.blockSignals(False)
        self.help_label.setText(providers.PROVIDER_HELP.get(provider, ""))

    def _refresh(self):
        provider = self._provider()
        key, base = self.key_edit.text(), self.base_edit.text()
        self.refresh_btn.setEnabled(False)
        self._worker = _Worker(
            lambda: providers.list_models(provider, key, base), self)
        self._worker.done.connect(self._models_ready)
        self._worker.failed.connect(self._refresh_failed)
        self._worker.start()

    def _models_ready(self, models):
        self.refresh_btn.setEnabled(True)
        if not models:
            QMessageBox.information(self, "AI Chat", "No models returned.")
            return
        current = self.model_combo.currentText()
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.setCurrentText(current if current in models
                                        else models[0])

    def _refresh_failed(self, message):
        self.refresh_btn.setEnabled(True)
        QMessageBox.warning(self, "AI Chat",
                            f"Could not list models:\n{message}")

    def _accept(self):
        provider = self._provider()
        self._settings.setValue("ai/provider", provider)
        self._settings.setValue(f"ai/key/{provider}", self.key_edit.text())
        self._settings.setValue(f"ai/base/{provider}", self.base_edit.text())
        if self.model_combo.currentText():
            self._settings.setValue(f"ai/model/{provider}",
                                    self.model_combo.currentText())
        self.accept()


# ---------------------------------------------------------------- input
class _ChatInput(QPlainTextEdit):
    """Multi-line input that submits on Enter (Shift+Enter = newline) and
    recalls previously sent prompts with Up/Down (at the first/last line)."""

    submitted = Signal()
    history_prev = Signal()
    history_next = Signal()

    def keyPressEvent(self, event):
        if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and not event.modifiers() & Qt.ShiftModifier):
            self.submitted.emit()
            return
        cursor = self.textCursor()
        if event.key() == Qt.Key_Up and cursor.blockNumber() == 0:
            self.history_prev.emit()
            return
        if (event.key() == Qt.Key_Down
                and cursor.blockNumber() == self.document().blockCount() - 1):
            self.history_next.emit()
            return
        super().keyPressEvent(event)


# ---------------------------------------------------------------- dock
class AiDock(QDockWidget):
    """Hideable AI chat side panel that writes LaTeX into the editor.

    *get_editor* is a zero-arg callable returning the DocumentEditor to
    write into (a callable, not the editor itself, so the dock always
    targets the window's current editor)."""

    def __init__(self, get_editor, parent=None):
        super().__init__("AI Chat", parent)
        self._get_editor = get_editor
        self.setObjectName("AiAssistant")
        self._worker = None
        self._is_busy = False
        self._think_dots = 0
        self._think_timer = QTimer(self)
        self._think_timer.setInterval(400)
        self._think_timer.timeout.connect(self._tick)
        self._history = []
        self._sent = []                 # past user prompts (Up/Down recall)
        self._hist_index = None
        self._draft = ""
        self._settings = QSettings(*_SETTINGS)
        self._font_pt = int(self._settings.value("ai/fontpt", 10))

        self.body = body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(2)
        header.addWidget(QLabel("<b>AI Assistant</b>"))
        self.provider_label = QLabel()
        self.provider_label.setStyleSheet("color:#888;")
        header.addWidget(self.provider_label, 1)
        self.smaller_btn = self._tool("A−", "Smaller text",
                                       lambda: self._change_font(-1))
        self.larger_btn = self._tool("A+", "Larger text",
                                     lambda: self._change_font(1))
        self.help_btn = self._tool("?", "Help", self._show_help,
                                   "mdi.help-circle-outline")
        self.settings_btn = self._tool("⚙", "AI Chat settings",
                                       self._open_settings, "mdi.cog-outline")
        self.clear_btn = self._tool("✕", "Clear chat", self._clear,
                                    "mdi.notification-clear-all")
        for btn in (self.smaller_btn, self.larger_btn, self.help_btn,
                    self.settings_btn, self.clear_btn):
            header.addWidget(btn)
        layout.addLayout(header)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(True)
        layout.addWidget(self.transcript, 1)

        self.thinking_label = QLabel()
        self.thinking_label.setStyleSheet("color:#2e7d4f; font-style:italic;")
        self.thinking_label.setVisible(False)
        layout.addWidget(self.thinking_label)

        input_row = QHBoxLayout()
        self.input = _ChatInput()
        self.input.setPlaceholderText(
            "Ask the AI to write or edit…  (Enter sends, Shift+Enter = newline)")
        self.input.setFixedHeight(70)
        self.send_btn = self._tool("Send", "Send", self._send_or_stop,
                                   "mdi.send")
        self.send_btn.setIconSize(QSize(24, 24))
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.send_btn, 0, Qt.AlignBottom)
        layout.addLayout(input_row)

        # A thin collapse strip on the LEFT edge: click to fold the panel
        # to a sliver and click again to expand it (like a sidebar).
        outer = QWidget()
        row = QHBoxLayout(outer)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._collapsed = False
        self._expanded_w = 360
        self.collapse_btn = QToolButton()
        self.collapse_btn.setAutoRaise(True)
        self.collapse_btn.setArrowType(Qt.RightArrow)
        self.collapse_btn.setToolTip("Collapse the chat panel")
        self.collapse_btn.setFixedWidth(16)
        self.collapse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        row.addWidget(self.collapse_btn)
        row.addWidget(body, 1)
        self.setWidget(outer)

        self.input.submitted.connect(self._send)
        self.input.history_prev.connect(self._history_prev)
        self.input.history_next.connect(self._history_next)

        self._apply_font()
        self._update_status()
        self._load_history()

    # ------------------------------------------------------- collapse
    def _toggle_collapse(self):
        """Fold the panel to a thin edge strip, or expand it back."""
        main = self.parent() if isinstance(self.parent(), QMainWindow) else None
        if not self._collapsed:
            self._expanded_w = max(self.width(), 220)
            self.body.setVisible(False)
            self.collapse_btn.setArrowType(Qt.LeftArrow)
            self.collapse_btn.setToolTip("Expand the chat panel")
            self.setFixedWidth(self.collapse_btn.width() + 6)
            self._collapsed = True
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.body.setVisible(True)
            self.collapse_btn.setArrowType(Qt.RightArrow)
            self.collapse_btn.setToolTip("Collapse the chat panel")
            self._collapsed = False
            if main is not None:
                main.resizeDocks([self], [self._expanded_w], Qt.Horizontal)

    def _tool(self, text, tip, slot, glyph=None):
        btn = QToolButton()
        ico = _icon(glyph) if glyph else None
        if ico is not None:
            btn.setIcon(ico)
        elif text:
            btn.setText(text)
        btn.setToolTip(tip)
        btn.setAutoRaise(True)
        btn.clicked.connect(slot)
        return btn

    # ------------------------------------------------------- settings
    def _open_settings(self):
        if AiSettingsDialog(self).exec():
            self._update_status()

    def _update_status(self):
        provider = self._settings.value("ai/provider", "Claude")
        self.provider_label.setText(
            providers.DISPLAY_NAMES.get(provider, provider))

    def _change_font(self, delta):
        self._font_pt = max(7, min(28, self._font_pt + delta))
        self._settings.setValue("ai/fontpt", self._font_pt)
        self._apply_font()

    def _apply_font(self):
        for widget in (self.transcript, self.input):
            font = widget.font()
            font.setPointSize(self._font_pt)
            widget.setFont(font)

    # ------------------------------------------------------- persistence
    def _save_history(self):
        # keep the last 100 turns so the store stays small
        self._settings.setValue("ai/history",
                                json.dumps(self._history[-100:]))
        self._settings.sync()           # flush now so a hard close keeps it

    def _load_history(self):
        raw = self._settings.value("ai/history", "")
        try:
            self._history = json.loads(raw) if raw else []
        except (ValueError, TypeError):
            self._history = []
        self._sent = [m["content"] for m in self._history
                      if m.get("role") == "user"]
        if self._history:
            for msg in self._history:
                if msg.get("role") == "user":
                    self._log("you", msg.get("content", ""))
                elif msg.get("role") == "assistant":
                    prose = prose_only(msg.get("content", ""))
                    self._log("ai", prose or "(inserted LaTeX)")
        else:
            self._welcome()

    def _welcome(self):
        self._log("system",
                  "Hello! I can help you write your document — ask me to draft "
                  "a section, an abstract, a table or an equation and I'll "
                  "insert it at the cursor. Set your provider (Anthropic, "
                  "OpenAI, Mistral, Ollama or Local) and API key via the gear "
                  "icon.")

    def _show_help(self):
        self._log("system",
                  "Ask in plain English, e.g. “write an introduction "
                  "about photosynthesis with two paragraphs and a bulleted "
                  "list”. The reply's LaTeX is imported and inserted at "
                  "the cursor as real, editable content. A−/A+ resize this "
                  "text; the gear sets the provider/model/key; the ✕ icon "
                  "clears the chat. Use the arrow on the left edge to collapse "
                  "the panel.")

    def _clear(self):
        self.transcript.clear()
        self._history = []
        self._sent = []
        self._hist_index = None
        self._draft = ""
        self._save_history()
        self._welcome()

    # ------------------------------------------------------- transcript
    def _log(self, role, text):
        colours = {"you": "#2176c7", "ai": "#2e7d4f",
                   "system": "#888", "error": "#c0392b"}
        who = {"you": "You", "ai": "Assistant", "system": "",
               "error": "Error"}.get(role, role)
        prefix = f"<b style='color:{colours.get(role, '#000')}'>{who}:</b> " \
            if who else ""
        safe = (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\n", "<br>"))
        self.transcript.append(
            f"<div style='margin:4px 0;'>{prefix}{safe}</div>")

    def _busy(self, busy):
        self._is_busy = busy
        if busy:
            self._think_dots = 0
            self.thinking_label.setText("Assistant is thinking")
            self.thinking_label.setVisible(True)
            self._think_timer.start()
            self._set_send("mdi.stop", "■", "Stop")
        else:
            self._think_timer.stop()
            self.thinking_label.setVisible(False)
            self._set_send("mdi.send", "Send", "Send")

    def _set_send(self, glyph, fallback, tip):
        ico = _icon(glyph)
        if ico is not None:
            self.send_btn.setIcon(ico)
            self.send_btn.setText("")
        else:
            self.send_btn.setText(fallback)
        self.send_btn.setToolTip(tip)

    def _tick(self):
        self._think_dots = (self._think_dots + 1) % 4
        self.thinking_label.setText("Assistant is thinking"
                                    + "." * self._think_dots)

    def _send_or_stop(self):
        self._stop() if self._is_busy else self._send()

    def _stop(self):
        """Abandon the in-flight request (its late result is ignored)."""
        if self._worker is not None:
            for sig in (self._worker.done, self._worker.failed):
                try:
                    sig.disconnect()
                except (TypeError, RuntimeError):
                    pass
            self._worker = None
        self._busy(False)
        self._log("system", "Stopped.")

    # ------------------------------------------------------- history
    def _history_prev(self):
        if not self._sent:
            return
        if self._hist_index is None:
            self._draft = self.input.toPlainText()
            self._hist_index = len(self._sent) - 1
        elif self._hist_index > 0:
            self._hist_index -= 1
        self._set_input(self._sent[self._hist_index])

    def _history_next(self):
        if self._hist_index is None:
            return
        if self._hist_index < len(self._sent) - 1:
            self._hist_index += 1
            self._set_input(self._sent[self._hist_index])
        else:
            self._hist_index = None
            self._set_input(self._draft)

    def _set_input(self, text):
        self.input.setPlainText(text)
        cursor = self.input.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.input.setTextCursor(cursor)

    # ------------------------------------------------------- actions
    def _send(self):
        if self._is_busy:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        provider = self._settings.value("ai/provider", "Claude")
        model = self._settings.value(f"ai/model/{provider}", "")
        key = self._settings.value(f"ai/key/{provider}", "")
        base = self._settings.value(f"ai/base/{provider}", "")
        if not model:
            self._log("error", "Open Settings and choose a model first.")
            return
        if provider in providers.NEEDS_KEY and not key.strip():
            self._log("error", "Set your API key for this provider in "
                               "Settings (the gear icon).")
            return

        self.input.clear()
        self._sent.append(text)
        self._hist_index = None
        self._draft = ""
        self._log("you", text)
        self._history.append({"role": "user", "content": text})
        self._save_history()

        editor = self._get_editor()
        docclass = "article"
        summary = "nothing yet"
        if editor is not None:
            try:
                doc = editor.get_document()
                docclass = doc.meta.documentclass or "article"
                summary = document_summary(doc)
            except Exception:               # pragma: no cover - defensive
                pass
        # Substitute placeholders with str.replace, NOT str.format — the
        # prompt contains literal LaTeX braces (\section{...}) that
        # str.format would misread as fields and raise.
        system = (SYSTEM_PROMPT
                  .replace("{docclass}", str(docclass))
                  .replace("{summary}", summary))
        messages = [{"role": "system", "content": system}] + self._history
        self._busy(True)
        self._run(lambda: providers.chat(provider, model, messages, key, base),
                  self._reply_ready)

    def _reply_ready(self, reply):
        self._busy(False)
        self._history.append({"role": "assistant", "content": reply})
        self._save_history()
        latex = extract_latex(reply)
        prose = prose_only(reply)
        if latex:
            self._insert_latex(latex, prose)
        else:
            self._log("ai", prose or reply)

    def _insert_latex(self, latex, prose):
        editor = self._get_editor()
        if editor is None:
            self._log("ai", prose or "(no editor to write into)")
            return
        try:
            blocks = import_body_fragment(latex)
        except Exception as exc:            # pragma: no cover - parser guard
            self._log("ai", prose or "Done.")
            self._log("error", f"Could not parse the generated LaTeX: {exc}")
            return
        if not blocks:
            # The fence held nothing the importer recognised — show the
            # prose (or the raw snippet) rather than silently doing nothing.
            self._log("ai", prose or latex)
            return
        editor.insert_blocks(blocks)
        self._log("ai", prose or "Done.")
        self._log("system", f"Inserted {len(blocks)} block(s) into the "
                            f"document.")

    # ------------------------------------------------------- threading
    def _run(self, fn, on_done):
        worker = _Worker(fn, self)
        worker.done.connect(on_done)
        worker.failed.connect(self._on_error)
        worker.finished.connect(lambda: self._clear_worker(worker))
        self._worker = worker
        worker.start()

    def _on_error(self, message):
        self._busy(False)
        self._log("error", message)

    def _clear_worker(self, worker):
        if self._worker is worker:
            self._worker = None

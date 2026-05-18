"""Named theme presets — palette colours, tab QSS, editor/status styling.

Each theme is a dict of named colour keys consumed by apply_theme() to
build a QPalette and by the QSS generators to style tabs, the editor
page/desk, and the status bar.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


# ------------------------------------------------------------------ #
# Theme definitions                                                    #
# ------------------------------------------------------------------ #

THEMES: dict[str, dict[str, str]] = {
    "Light": {
        "dark": "0",
        "base":         "#ffffff",
        "surface":      "#f7f7f7",
        "text":         "#1c1c1c",
        "text_muted":   "#666666",
        "accent":       "#1a6dd8",
        "accent2":      "#d96b00",
        "link":         "#1a6dd8",
        "highlight":    "#1a6dd8",
        "highlight_text": "#ffffff",
        "bright_text":  "#ff3333",
        "disabled":     "#9a9a9a",
        "placeholder":  "#888888",
        "alt_base":     "#eef1f5",
        "tab_active":   "#ffffff",
        "tab_inactive": "#e4e4e4",
        "tab_hover":    "#ececec",
        "desk_bg":      "#d0d4d8",
        "page_bg":      "#ffffff",
        "page_border":  "#b8bcc1",
        "status_text":  "#444444",
    },
    "Solarized Light": {
        "dark": "0",
        "base":         "#fdf6e3",
        "surface":      "#eee8d5",
        "text":         "#657b83",
        "text_muted":   "#93a1a1",
        "accent":       "#268bd2",
        "accent2":      "#cb4b16",
        "link":         "#268bd2",
        "highlight":    "#268bd2",
        "highlight_text": "#fdf6e3",
        "bright_text":  "#dc322f",
        "disabled":     "#93a1a1",
        "placeholder":  "#93a1a1",
        "alt_base":     "#eee8d5",
        "tab_active":   "#fdf6e3",
        "tab_inactive": "#e8e1ce",
        "tab_hover":    "#f0e9d5",
        "desk_bg":      "#d5cdb8",
        "page_bg":      "#fdf6e3",
        "page_border":  "#c9c1a8",
        "status_text":  "#657b83",
    },
    "Sepia": {
        "dark": "0",
        "base":         "#f5efe0",
        "surface":      "#ebe4d3",
        "text":         "#5b4636",
        "text_muted":   "#8a7560",
        "accent":       "#8b5e3c",
        "accent2":      "#b07038",
        "link":         "#7a5025",
        "highlight":    "#8b5e3c",
        "highlight_text": "#f5efe0",
        "bright_text":  "#c0392b",
        "disabled":     "#b0a08a",
        "placeholder":  "#a09080",
        "alt_base":     "#e8e0d0",
        "tab_active":   "#f5efe0",
        "tab_inactive": "#e0d7c6",
        "tab_hover":    "#ebe2d0",
        "desk_bg":      "#cdc4b2",
        "page_bg":      "#f5efe0",
        "page_border":  "#c5b9a5",
        "status_text":  "#6b5646",
    },
    "Dark": {
        "dark": "1",
        "base":         "#1e1e1e",
        "surface":      "#2d2d2d",
        "text":         "#d4d4d4",
        "text_muted":   "#858585",
        "accent":       "#4da6ff",
        "accent2":      "#f0a050",
        "link":         "#4da6ff",
        "highlight":    "#4da6ff",
        "highlight_text": "#ffffff",
        "bright_text":  "#ff5555",
        "disabled":     "#606060",
        "placeholder":  "#777777",
        "alt_base":     "#3a3a3a",
        "tab_active":   "#2d2d2d",
        "tab_inactive": "#1e1e1e",
        "tab_hover":    "#383838",
        "desk_bg":      "#1a1a1a",
        "page_bg":      "#2d2d2d",
        "page_border":  "#555555",
        "status_text":  "#aaaaaa",
    },
    "Nord": {
        "dark": "1",
        "base":         "#2e3440",
        "surface":      "#3b4252",
        "text":         "#d8dee9",
        "text_muted":   "#7b88a1",
        "accent":       "#88c0d0",
        "accent2":      "#ebcb8b",
        "link":         "#88c0d0",
        "highlight":    "#88c0d0",
        "highlight_text": "#2e3440",
        "bright_text":  "#bf616a",
        "disabled":     "#616e88",
        "placeholder":  "#616e88",
        "alt_base":     "#434c5e",
        "tab_active":   "#3b4252",
        "tab_inactive": "#2e3440",
        "tab_hover":    "#434c5e",
        "desk_bg":      "#242933",
        "page_bg":      "#3b4252",
        "page_border":  "#4c566a",
        "status_text":  "#a0aec0",
    },
    "Dracula": {
        "dark": "1",
        "base":         "#282a36",
        "surface":      "#44475a",
        "text":         "#f8f8f2",
        "text_muted":   "#8a8d9e",
        "accent":       "#bd93f9",
        "accent2":      "#ffb86c",
        "link":         "#8be9fd",
        "highlight":    "#bd93f9",
        "highlight_text": "#282a36",
        "bright_text":  "#ff5555",
        "disabled":     "#6272a4",
        "placeholder":  "#6272a4",
        "alt_base":     "#383a4a",
        "tab_active":   "#44475a",
        "tab_inactive": "#282a36",
        "tab_hover":    "#383a4a",
        "desk_bg":      "#1e1f29",
        "page_bg":      "#44475a",
        "page_border":  "#6272a4",
        "status_text":  "#bfc0cc",
    },
}

THEME_NAMES: list[str] = list(THEMES.keys())


def is_dark(theme_name: str) -> bool:
    return THEMES.get(theme_name, THEMES["Light"])["dark"] == "1"


# ------------------------------------------------------------------ #
# QPalette builder                                                     #
# ------------------------------------------------------------------ #

def apply_theme(app: QApplication, theme_name: str) -> dict[str, str]:
    """Set the Fusion style + QPalette for the given theme. Returns the
    theme dict so callers can feed it to the QSS generators."""
    app.setStyle("Fusion")
    t = THEMES.get(theme_name, THEMES["Light"])
    pal = QPalette()

    pal.setColor(QPalette.Window,          QColor(t["surface"]))
    pal.setColor(QPalette.WindowText,      QColor(t["text"]))
    pal.setColor(QPalette.Base,            QColor(t["base"]))
    pal.setColor(QPalette.AlternateBase,   QColor(t["alt_base"]))
    pal.setColor(QPalette.ToolTipBase,     QColor(t["surface"]))
    pal.setColor(QPalette.ToolTipText,     QColor(t["text"]))
    pal.setColor(QPalette.Text,            QColor(t["text"]))
    pal.setColor(QPalette.Button,          QColor(t["surface"]))
    pal.setColor(QPalette.ButtonText,      QColor(t["text"]))
    pal.setColor(QPalette.BrightText,      QColor(t["bright_text"]))
    pal.setColor(QPalette.Link,            QColor(t["link"]))
    pal.setColor(QPalette.Highlight,       QColor(t["highlight"]))
    pal.setColor(QPalette.HighlightedText, QColor(t["highlight_text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(t["placeholder"]))

    disabled_color = QColor(t["disabled"])
    pal.setColor(QPalette.Disabled, QPalette.WindowText, disabled_color)
    pal.setColor(QPalette.Disabled, QPalette.Text,       disabled_color)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_color)
    pal.setColor(QPalette.Disabled, QPalette.Highlight,  disabled_color)

    app.setPalette(pal)
    return t


# ------------------------------------------------------------------ #
# QSS generators                                                      #
# ------------------------------------------------------------------ #

def tab_stylesheet(t: dict[str, str]) -> str:
    """Polished tab bar styling with accent-coloured active indicator."""
    return f"""
        QTabWidget::pane {{
            border-top: 2px solid {t["accent"]};
            background: {t["base"]};
        }}
        QTabBar::tab {{
            background: {t["tab_inactive"]};
            color: {t["text_muted"]};
            padding: 7px 20px;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
            margin-right: 2px;
            border: 1px solid transparent;
            border-bottom: none;
        }}
        QTabBar::tab:selected {{
            background: {t["tab_active"]};
            color: {t["text"]};
            border: 1px solid {t["accent"]};
            border-bottom: 2px solid {t["tab_active"]};
            font-weight: bold;
        }}
        QTabBar::tab:hover:!selected {{
            background: {t["tab_hover"]};
            color: {t["text"]};
        }}
    """


def editor_page_stylesheet(t: dict[str, str]) -> str:
    return f"#page {{ background: {t['page_bg']}; border: 1px solid {t['page_border']}; }}"


def editor_desk_stylesheet(t: dict[str, str]) -> str:
    return f"#desk {{ background: {t['desk_bg']}; }}"


def editor_textedit_stylesheet(t: dict[str, str]) -> str:
    return f"QTextEdit {{ background: {t['page_bg']}; color: {t['text']}; border: none; }}"


def latex_view_stylesheet(t: dict[str, str]) -> str:
    return f"QPlainTextEdit {{ background: {t['base']}; color: {t['text']}; }}"


def status_label_stylesheet(t: dict[str, str]) -> str:
    return f"color: {t['status_text']}; padding: 0 6px;"

"""Modern Hacker Terminal HUD Stylesheet and Palette for JARVIS.

Designed for Windows Terminal / Cascadia Code dark aesthetic:
- Deep obsidian surface with electric cyan (#00f0ff) and terminal green (#10b981) accents.
- Custom styled QTabBar, QScrollArea, QLineEdit, QPushButton, and QTableWidget.
"""

TERMINAL_THEME_QSS = """
/* Global Window & Base Surface */
QMainWindow, QWidget#CentralWidget, QWidget#TerminalContainer {
    background-color: #0a0a0c;
    color: #e4e4e7;
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", "Courier New", monospace;
    font-size: 13px;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

/* Custom Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0a0a0c;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #27272a;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #00f0ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Top Header Bar */
QFrame#TerminalHeader {
    background-color: #121216;
    border-bottom: 1px solid #1e1e24;
    padding: 6px 14px;
}

QLabel#TerminalTitle {
    color: #00f0ff;
    font-weight: 800;
    font-size: 14px;
    letter-spacing: 1.5px;
}

QLabel#TerminalSubtitle {
    color: #71717a;
    font-size: 11px;
}

/* Header Status Pills & Toggle Buttons */
QPushButton#HeaderPillButton {
    background-color: #18181f;
    color: #a1a1aa;
    border: 1px solid #272730;
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#HeaderPillButton:hover {
    background-color: #22222c;
    color: #ffffff;
    border-color: #3b82f6;
}

QLabel#TelemetryPill {
    background-color: #16161c;
    color: #38bdf8;
    border: 1px solid #22222a;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* Main Tab Bar Styling */
QTabWidget::pane {
    border: none;
    background-color: #0a0a0c;
}

QTabBar::tab {
    background-color: #121216;
    color: #71717a;
    border: 1px solid #1e1e24;
    border-bottom: none;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #181820;
    color: #00f0ff;
    border-top: 2px solid #00f0ff;
    border-left: 1px solid #2a2a36;
    border-right: 1px solid #2a2a36;
}

QTabBar::tab:hover:!selected {
    background-color: #16161c;
    color: #d4d4d8;
}

/* Console Message Stream Area */
QTextBrowser#ConsoleLogArea {
    background-color: #0d0d11;
    color: #f4f4f5;
    border: 1px solid #1c1c24;
    border-radius: 8px;
    padding: 12px;
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
    line-height: 1.5;
}

/* Terminal Command Input Bar */
QFrame#TerminalInputFrame {
    background-color: #121216;
    border: 1px solid #242430;
    border-radius: 8px;
    padding: 4px 10px;
}
QFrame#TerminalInputFrame:focus-within {
    border: 1px solid #00f0ff;
    background-color: #15151b;
}

QLabel#TerminalPromptPrefix {
    color: #10b981;
    font-weight: 800;
    font-size: 14px;
    padding-right: 6px;
}

QLineEdit#TerminalLineEdit {
    background-color: transparent;
    color: #ffffff;
    border: none;
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
}

QPushButton#TerminalIconButton {
    background-color: #1c1c24;
    color: #a1a1aa;
    border: 1px solid #282834;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#TerminalIconButton:hover {
    background-color: #272734;
    color: #00f0ff;
    border-color: #00f0ff;
}

/* Cards & Containers in Todo / Janitor / Proactive Tabs */
QFrame#HackerCard {
    background-color: #121216;
    border: 1px solid #1e1e26;
    border-radius: 8px;
    padding: 14px;
}

QLabel#CardHeaderTitle {
    color: #00f0ff;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.5px;
}

/* Action Primary Buttons */
QPushButton#TerminalActionButton {
    background-color: #00f0ff;
    color: #0a0a0c;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.5px;
}
QPushButton#TerminalActionButton:hover {
    background-color: #38bdf8;
}
QPushButton#TerminalActionButton:disabled {
    background-color: #27272a;
    color: #71717a;
}

/* Todo List / Task Item Styling */
QListWidget#TerminalListWidget {
    background-color: #0d0d11;
    border: 1px solid #1c1c24;
    border-radius: 8px;
    padding: 6px;
    color: #e4e4e7;
}

QListWidget#TerminalListWidget::item {
    background-color: #14141a;
    border: 1px solid #202028;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 6px;
}
QListWidget#TerminalListWidget::item:hover {
    border-color: #00f0ff;
    background-color: #181822;
}

/* Footer Telemetry Status */
QFrame#TerminalFooter {
    background-color: #0e0e12;
    border-top: 1px solid #1a1a22;
    padding: 4px 12px;
}
QLabel#FooterStatusLabel {
    color: #71717a;
    font-size: 11px;
}
"""

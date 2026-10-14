"""Theme configuration and stylesheets for JARVIS Desktop GUI.

Style: Claude Desktop Ultra-Minimalist Edition (Deep Obsidian & Slate).
Clean, single-window conversational canvas with floating input pill and smooth typography.
"""

DEEP_OBSIDIAN_THEME_QSS = """
/* Global Window Styling */
QMainWindow, QWidget#CentralWidget {
    background-color: #0f0f11;
    color: #f4f4f5;
    font-family: "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 14px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

/* Header Container */
QFrame#HeaderBar {
    background-color: #0f0f11;
    border-bottom: 1px solid #1e1e22;
    padding: 8px 16px;
}

QLabel#HeaderTitle {
    color: #f4f4f5;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#HeaderSubtitle {
    color: #71717a;
    font-size: 12px;
}

/* Status Pill */
QLabel#StatusPill {
    background-color: #18181b;
    color: #a1a1aa;
    border: 1px solid #27272a;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* Scroll Area for Messages */
QScrollArea#ChatScrollArea {
    background-color: transparent;
    border: none;
}

QWidget#ChatScrollContent {
    background-color: transparent;
}

/* Custom Sleek Scrollbar */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #27272a;
    min-height: 25px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #3f3f46;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Message Bubbles */
QFrame#UserBubble {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 16px;
    padding: 12px 16px;
    margin-left: 80px;
    margin-right: 4px;
}

QFrame#AssistantBubble {
    background-color: #18181b;
    border: 1px solid #222226;
    border-radius: 16px;
    padding: 14px 18px;
    margin-right: 80px;
    margin-left: 4px;
}

QLabel#BubbleSender {
    font-size: 11px;
    font-weight: 700;
    color: #a1a1aa;
    margin-bottom: 4px;
}

QLabel#BubbleText {
    color: #f4f4f5;
    font-size: 14px;
    line-height: 1.5;
}

/* Floating Input Pill Container */
QFrame#InputPillContainer {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 24px;
    padding: 6px 14px;
}

QFrame#InputPillContainer:focus-within {
    border: 1px solid #38bdf8;
    background-color: #1a1a1e;
}

/* Inner Text Area */
QTextEdit#InputTextEdit {
    background-color: transparent;
    color: #f4f4f5;
    border: none;
    font-size: 14px;
    line-height: 1.4;
    padding: 4px 6px;
}

/* Action Buttons inside Input Pill */
QPushButton#MicButton {
    background-color: transparent;
    color: #a1a1aa;
    border: none;
    border-radius: 18px;
    padding: 6px;
    font-size: 15px;
}

QPushButton#MicButton:hover {
    background-color: #27272a;
    color: #38bdf8;
}

QPushButton#MicButton[listening="true"] {
    background-color: #dc2626;
    color: #ffffff;
}

QPushButton#SendButton {
    background-color: #38bdf8;
    color: #09090b;
    border: none;
    border-radius: 18px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#SendButton:hover {
    background-color: #7dd3fc;
}

QPushButton#SendButton:disabled {
    background-color: #27272a;
    color: #71717a;
}

/* Minimal Header Buttons */
QPushButton#HeaderIconButton {
    background-color: transparent;
    color: #71717a;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}

QPushButton#HeaderIconButton:hover {
    background-color: #18181b;
    color: #e4e4e7;
}

/* Footer Hint */
QLabel#FooterHint {
    color: #52525b;
    font-size: 11px;
    text-align: center;
}
"""

DARK_THEME_QSS = DEEP_OBSIDIAN_THEME_QSS

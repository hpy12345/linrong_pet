from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel


class SpeechBubble(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWordWrap(True)
        self.setMaximumWidth(260)
        self.setStyleSheet(
            """
            QLabel {
                color: #2f2a32;
                background: rgba(255, 250, 252, 238);
                border: 1px solid rgba(92, 60, 83, 90);
                border-radius: 13px;
                padding: 9px 12px;
                font-family: "Microsoft YaHei UI";
                font-size: 14px;
            }
            """
        )
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def show_message(self, text: str, anchor, duration_ms: int = 2500) -> None:
        self.setText(text)
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        x = anchor.x() + (anchor.width() - self.width()) // 2
        y = anchor.y() - self.height() - 8
        x = max(screen.left(), min(x, screen.right() - self.width() + 1))
        if y < screen.top():
            y = anchor.y() + 16
        self.move(QPoint(x, y))
        self.show()
        self.raise_()
        self.hide_timer.start(duration_ms)


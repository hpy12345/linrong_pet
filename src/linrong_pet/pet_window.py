from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


def is_drag_delta(delta: QPoint) -> bool:
    return delta.manhattanLength() > 4


class PetWindow(QWidget):
    clicked = Signal()
    drag_started = Signal()
    drag_finished = Signal(QPoint)
    hover_started = Signal()
    hover_ended = Signal()

    def __init__(self, pet_height: int) -> None:
        super().__init__()
        self.pet_height = pet_height
        self._press_global: QPoint | None = None
        self._press_window: QPoint | None = None
        self._dragging = False

        self.setWindowTitle("林榕")
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        self.sprite = QLabel(self)
        self.sprite.setAlignment(Qt.AlignCenter)
        self.sprite.setAttribute(Qt.WA_TranslucentBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.sprite)
        self.set_pet_height(pet_height)

    def set_pet_height(self, height: int) -> None:
        self.pet_height = height
        width = round(height * 192 / 208)
        self.setFixedSize(width, height)

    def set_frame(self, frame: QPixmap) -> None:
        self.sprite.setPixmap(frame)

    def available_geometry(self):
        return QApplication.primaryScreen().availableGeometry()

    def clamped_position(self, requested: QPoint) -> QPoint:
        bounds = self.available_geometry()
        max_x = bounds.right() - self.width() + 1
        max_y = bounds.bottom() - self.height() + 1
        return QPoint(
            max(bounds.left(), min(requested.x(), max_x)),
            max(bounds.top(), min(requested.y(), max_y)),
        )

    def clamp_to_primary_screen(self) -> None:
        self.move(self.clamped_position(self.pos()))

    def floor_y(self) -> int:
        return self.available_geometry().bottom() - self.height() + 1

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_window = self.pos()
            self._dragging = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._press_global is not None
            and self._press_window is not None
            and event.buttons() & Qt.LeftButton
        ):
            delta = event.globalPosition().toPoint() - self._press_global
            if not self._dragging and is_drag_delta(delta):
                self._dragging = True
                self.drag_started.emit()
            if self._dragging:
                self.move(self.clamped_position(self._press_window + delta))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._press_global is not None:
            if self._dragging:
                self.drag_finished.emit(self.pos())
            else:
                self.clicked.emit()
            self._press_global = None
            self._press_window = None
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self.hover_started.emit()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover_ended.emit()
        super().leaveEvent(event)

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from linrong_pet.pet_window import PetWindow, is_drag_delta


def test_drag_threshold():
    assert not is_drag_delta(QPoint(2, 2))
    assert is_drag_delta(QPoint(3, 2))


def test_clamp_keeps_pet_inside_primary_screen(qtbot):
    window = PetWindow(320)
    qtbot.addWidget(window)
    bounds = window.available_geometry()

    top_left = window.clamped_position(QPoint(-100000, -100000))
    bottom_right = window.clamped_position(QPoint(100000, 100000))

    assert top_left.x() == bounds.left()
    assert top_left.y() == bounds.top()
    assert bottom_right.x() + window.width() - 1 == bounds.right()
    assert bottom_right.y() + window.height() - 1 == bounds.bottom()


def test_window_is_transparent_frameless_tool_and_always_on_top(qtbot):
    window = PetWindow(320)
    qtbot.addWidget(window)

    assert window.testAttribute(Qt.WA_TranslucentBackground)
    assert window.windowFlags() & Qt.Tool
    assert window.windowFlags() & Qt.FramelessWindowHint
    assert window.windowFlags() & Qt.WindowStaysOnTopHint


def test_mouse_click_and_drag_are_distinguished(qtbot):
    window = PetWindow(320)
    qtbot.addWidget(window)
    window.move(100, 100)
    clicked = []
    drag_started = []
    drag_finished = []
    window.clicked.connect(lambda: clicked.append(True))
    window.drag_started.connect(lambda: drag_started.append(True))
    window.drag_finished.connect(lambda point: drag_finished.append(point))

    press = QMouseEvent(
        QEvent.MouseButtonPress,
        QPointF(40, 40),
        QPointF(140, 140),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    release = QMouseEvent(
        QEvent.MouseButtonRelease,
        QPointF(40, 40),
        QPointF(140, 140),
        Qt.LeftButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    window.mousePressEvent(press)
    window.mouseReleaseEvent(release)
    assert clicked == [True]
    assert drag_started == []

    press = QMouseEvent(
        QEvent.MouseButtonPress,
        QPointF(40, 40),
        QPointF(140, 140),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    move = QMouseEvent(
        QEvent.MouseMove,
        QPointF(55, 48),
        QPointF(155, 148),
        Qt.NoButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    release = QMouseEvent(
        QEvent.MouseButtonRelease,
        QPointF(55, 48),
        QPointF(155, 148),
        Qt.LeftButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    window.mousePressEvent(press)
    window.mouseMoveEvent(move)
    window.mouseReleaseEvent(release)

    assert drag_started == [True]
    assert len(drag_finished) == 1
    assert window.pos() == window.clamped_position(QPoint(115, 108))

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    activate_requested = Signal()

    def __init__(self, server_name: str = "LinRongPet.SingleInstance") -> None:
        super().__init__()
        self.server_name = server_name
        self.server: QLocalServer | None = None

    def claim(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if socket.waitForConnected(250):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(250)
            socket.disconnectFromServer()
            return False

        QLocalServer.removeServer(self.server_name)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.newConnection.connect(self._accept)
        return self.server.listen(self.server_name)

    def _accept(self) -> None:
        if self.server is None:
            return
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.waitForReadyRead(100)
            socket.readAll()
            socket.disconnectFromServer()
            socket.deleteLater()
            self.activate_requested.emit()


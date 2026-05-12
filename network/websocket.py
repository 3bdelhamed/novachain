from typing import Any, Dict, Optional, Set

from fastapi import WebSocket


class WebSocketManager:
    _instance: Optional["WebSocketManager"] = None

    def __new__(cls) -> "WebSocketManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.active_connections: Set[WebSocket] = set()
        return cls._instance

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        dead: Set[WebSocket] = set()
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self.active_connections.difference_update(dead)


ws_manager = WebSocketManager()
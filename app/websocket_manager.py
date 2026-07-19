from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # user_id -> list of active websockets
        self.active_connections = defaultdict(list)

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()

        print(f"✅ WebSocket connected: {user_id}")

        self.active_connections[user_id].append(websocket)

        print("ACTIVE USERS:", list(self.active_connections.keys()))

    def disconnect(self, user_id: str, websocket: WebSocket):
        if websocket in self.active_connections[user_id]:
            self.active_connections[user_id].remove(websocket)

        # cleanup empty lists
        if not self.active_connections[user_id]:
            del self.active_connections[user_id]

        print(f"❌ WebSocket disconnected: {user_id}")

    async def send_notification(self, user_id: str, payload: dict):
        print(f"📡 Sending notification to: {user_id}")
        print("ACTIVE CONNECTIONS:", list(self.active_connections.keys()))

        connections = self.active_connections.get(user_id, [])

        if not connections:
            print("⚠️ No active websocket for user:", user_id)
            return

        for websocket in connections:
            try:
                await websocket.send_json(payload)
                print("✅ Message sent")
            except Exception as e:
                print("❌ Failed sending websocket message:", e)


manager = ConnectionManager()
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Dict, List
import json

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.room_state: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
            self.room_state[room_id] = {"videoId": None, "time": 0, "status": "pause"}
            
        self.active_connections[room_id].append(websocket)
        
        current_state = self.room_state[room_id]
        if current_state["videoId"]:
            await websocket.send_text(json.dumps({
                "action": "sync",
                "videoId": current_state["videoId"],
                "time": current_state["time"],
                "status": current_state["status"]
            }))

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
                if room_id in self.room_state:
                    del self.room_state[room_id]

    async def broadcast(self, message: str, room_id: str, sender: WebSocket):
        try:
            data = json.loads(message)
            if data.get("action") == "load":
                self.room_state[room_id]["videoId"] = data.get("videoId")
                self.room_state[room_id]["time"] = 0
            elif data.get("action") in ["play", "pause"]:
                self.room_state[room_id]["status"] = data.get("action")
                self.room_state[room_id]["time"] = data.get("time", 0)
        except Exception:
            pass

        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection != sender:
                    await connection.send_text(message)

manager = ConnectionManager()

@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data, room_id, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
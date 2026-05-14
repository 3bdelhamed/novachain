import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from api.routes import router
from api.demo_routes import router as demo_router
from core.instance import get_blockchain
from storage.sqlite import SQLiteStorage
from network.discovery import p2p_discovery_loop

PORT = os.environ.get("PORT", "8000")

# ── Lifespan Manager ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    discovery_task = asyncio.create_task(p2p_discovery_loop())
    yield
    discovery_task.cancel()
# ───────────────────────────────────────────────────────────────────────────

app = FastAPI(title="NovaChain Enterprise", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static React UI (Safe: only mount if build exists) ─────────────────────
STATIC_DIR = "static"
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")
INDEX_FILE = os.path.join(STATIC_DIR, "index.html")

if os.path.isdir(ASSETS_DIR) and os.path.isfile(INDEX_FILE):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

    @app.get("/")
    async def serve_react():
        return FileResponse(INDEX_FILE)
else:
    @app.get("/")
    async def no_ui():
        return JSONResponse({
            "status": "ok",
            "message": "NovaChain API is running.",
            "hint": "React UI not found. Build the UI (npm run build) and copy dist/ to static/ to enable the frontend."
        })
# ───────────────────────────────────────────────────────────────────────────

# Bootstrap singleton BEFORE mounting routes
db_path = f"./data/node_{PORT}.db"
os.makedirs("./data", exist_ok=True)

storage = SQLiteStorage(db_path)
get_blockchain(storage)

app.include_router(router)
app.include_router(demo_router)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(PORT), reload=True)
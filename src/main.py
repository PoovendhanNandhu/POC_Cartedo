"""FastAPI main application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.api.routes import router as api_router
from src.utils.config import config
import os

# Create FastAPI app
app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="Scenario-Aware JSON Re-Contextualization API using LangGraph and OpenAI"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1", tags=["transformation"])

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the web UI."""
    static_file = os.path.join(static_dir, "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    else:
        # Fallback to API info if no UI
        return {
            "name": config.APP_NAME,
            "version": config.APP_VERSION,
            "status": "running",
            "endpoints": {
                "transform": "/api/v1/transform/stream-openai",
                "validate": "/api/v1/validate",
                "health": "/api/v1/health",
                "scenarios": "/api/v1/scenarios",
                "ui": "/ui"
            }
        }


@app.get("/ui")
async def web_ui():
    """Serve the web UI."""
    static_file = os.path.join(static_dir, "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"error": "UI not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=config.LOG_LEVEL.lower())

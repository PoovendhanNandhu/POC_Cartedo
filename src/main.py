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

# Mount static files (with error handling for deployment)
try:
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        print(f"✅ Static files mounted from: {static_dir}")
    else:
        print(f"⚠️  Static directory not found: {static_dir}")
        static_dir = None
except Exception as e:
    print(f"⚠️  Could not mount static files: {e}")
    static_dir = None


@app.get("/")
async def root():
    """Serve the web UI or API info."""
    try:
        if static_dir and os.path.exists(static_dir):
            static_file = os.path.join(static_dir, "index.html")
            if os.path.exists(static_file):
                return FileResponse(static_file)
    except Exception as e:
        print(f"Error serving UI: {e}")

    # Fallback to API info
    return {
        "name": config.APP_NAME,
        "version": config.APP_VERSION,
        "status": "running",
        "endpoints": {
            "transform": "/api/v1/transform/stream-openai",
            "validate": "/api/v1/validate",
            "health": "/api/v1/health",
            "scenarios": "/api/v1/scenarios",
            "docs": "/docs",
            "ui": "/ui"
        }
    }


@app.get("/ui")
async def web_ui():
    """Serve the web UI."""
    try:
        if static_dir and os.path.exists(static_dir):
            static_file = os.path.join(static_dir, "index.html")
            if os.path.exists(static_file):
                return FileResponse(static_file)
    except Exception as e:
        print(f"Error serving UI: {e}")

    return {
        "error": "UI not found",
        "message": "Static files not available. Use /api/v1/* endpoints or /docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=config.LOG_LEVEL.lower())

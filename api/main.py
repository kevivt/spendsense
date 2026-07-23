"""
FastAPI entrypoint. Serves the JSON API under /api/* and the static
dashboard files at /.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import router

app = FastAPI(title="SpendSense API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local personal-use tool - fine to keep permissive
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

_dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")
if os.path.isdir(_dashboard_dir):
    app.mount("/", StaticFiles(directory=_dashboard_dir, html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)

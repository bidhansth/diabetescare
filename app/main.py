import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.routes import auth, entries, dashboard, medications, resources, admin, forum, carousel

app = FastAPI(title="DiabetesCare")

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
app.include_router(auth.router, prefix="/api/auth")
app.include_router(entries.router, prefix="/api/entries")
app.include_router(dashboard.router, prefix="/api/dashboard")
app.include_router(medications.router, prefix="/api/medications")
app.include_router(resources.router, prefix="/api/resources")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(forum.router, prefix="/api")
app.include_router(carousel.router, prefix="/api")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

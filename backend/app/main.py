from fastapi import FastAPI

from backend.app.routers import corpus, health

app = FastAPI(title="DIDI Platform API")
app.include_router(health.router)
app.include_router(corpus.router)

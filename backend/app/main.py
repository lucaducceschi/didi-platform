from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from backend.app.deps import get_current_user
from backend.app.routers import annotations, auth, codes, corpus, health, library, passages, projects, users

app = FastAPI(title="DIDI Platform API")


@app.exception_handler(IntegrityError)
def integrity_error(_: Request, __: IntegrityError) -> JSONResponse:
    # Checks catch ordinary cases with clear messages. This covers two people acting at the same moment.
    return JSONResponse({"detail": "This conflicts with a change someone else just made. Reload and try again."}, status_code=409)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(codes.router)
app.include_router(annotations.router)
app.include_router(library.router)
app.include_router(passages.router)
app.include_router(corpus.router, dependencies=[Depends(get_current_user)])

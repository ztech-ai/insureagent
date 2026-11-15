from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from insureagent_persistence.store import Conflict, Missing, Store, accounts
from sqlalchemy import select

from insureagent_api.config import Settings
from insureagent_api.modules.customers.router import router as customers
from insureagent_api.modules.identity.auth import router as identity
from insureagent_api.modules.records.router import router as records
from insureagent_api.modules.tasks.router import router as tasks


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="保知伴 AI", version="0.1.0-alpha", description="合成数据内部 Alpha")
    app.state.store = Store(settings.database_url, settings.data_key) if settings else None
    for router in (identity, customers, records, tasks):
        app.include_router(router)

    @app.exception_handler(Missing)
    async def missing(request: Request, exc: Missing):
        return JSONResponse(status_code=404, content={"detail": "not_found"})

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict):
        return JSONResponse(status_code=409, content={"detail": "version_conflict"})

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError):
        # Default errors echo input values; keep customer text out of error responses.
        return JSONResponse(status_code=422, content={"detail": "invalid_request"})

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "ok", "stage": "alpha", "synthetic_data_only": True}

    @app.get("/health/ready", tags=["health"], responses={503: {"description": "Not configured"}})
    def ready():
        if app.state.store is None:
            return JSONResponse(status_code=503, content={"status": "not_configured"})
        try:
            with app.state.store.transaction() as conn:
                conn.execute(select(accounts.c.id).limit(1))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "database_unavailable"})
        return {"status": "ready", "scope": "internal_alpha"}

    return app


app = create_app(Settings.from_env())

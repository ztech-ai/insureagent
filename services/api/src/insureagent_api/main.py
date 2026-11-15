from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="保知伴 AI", version="0.1.0", description="工程骨架，仅开放健康检查")


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok", "stage": "bootstrap"}


@app.get("/health/ready", tags=["health"], responses={503: {"description": "Not configured"}})
def ready() -> JSONResponse:
    # Do not advertise production readiness before persistence/auth/queue integration.
    return JSONResponse(
        status_code=503, content={"status": "not_ready", "reason": "bootstrap_only"}
    )

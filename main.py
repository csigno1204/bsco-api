# main.py (proxy générique déjà en place)
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseSettings
import httpx

class Settings(BaseSettings):
    SOFTR_ORIGIN: str
    BEXIO_API_BASE: str
    class Config:
        env_file = ".env"

settings = Settings()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.SOFTR_ORIGIN],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/api/bexio/{endpoint:path}")
async def proxy_bexio(
    endpoint: str,
    request: Request,
    token: str = Query(..., description="Bearer token dynamique")
):
    url = f"{settings.BEXIO_API_BASE}/{endpoint}"
    params = dict(request.query_params)
    params.pop("token", None)
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

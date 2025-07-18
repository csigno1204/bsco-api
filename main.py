from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict
import httpx

# --- Chargement des variables d'environnement via Render ---
class Settings(BaseSettings):
    # Domaine Softr autorisé (CORS)
    SOFTR_ORIGIN: str

    # URL de base de l'API Bexio
    BEXIO_BASE_URL: str

    # (Optionnel pour futures évolutions)
    SOFTR_API_KEY: str
    SOFTR_APP_ID: str
    SOFTR_DB_ID: str
    SOFTR_TABLE_ID: str

    # On ne lire plus de .env : tout vient de l'environnement Render
    model_config = SettingsConfigDict(env_file=None)

settings = Settings()

# --- Initialisation de l'application ---
app = FastAPI(
    title="Softr → Bexio Proxy",
    description="Proxy FastAPI pour relayer Softr vers l'API Bexio avec token dynamique",
    version="1.0.0"
)

# --- CORS : on n'autorise que Softr ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.SOFTR_ORIGIN],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# --- Health check (vérifier que le service est en ligne) ---
@app.get("/", summary="Health check")
async def health_check():
    return {"status": "ok"}

# --- Endpoint pour récupérer la liste des contacts (clients) Bexio ---
@app.get("/api/bexio/contacts", summary="Liste des clients Bexio")
async def get_contacts(
    token: str = Query(..., description="Bearer token issu de Softr ({{Token}})")
):
    """
    Appelle GET /contacts sur l'API Bexio avec le token passé en query-string.
    """
    url = f"{settings.BEXIO_BASE_URL}/contacts"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)

    if resp.status_code >= 400:
        # Propagation de l'erreur Bexio vers Softr
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp.json()

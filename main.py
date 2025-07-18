from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic_settings import BaseSettings, SettingsConfigDict
import httpx
import time

# --- 3.1. Chargement des settings depuis l'environnement Render ---
class Settings(BaseSettings):
    SOFTR_ORIGIN: str         # Domaine Softr pour CORS
    BEXIO_BASE_URL: str       # Base URL de l'API Bexio
    CLIENT_ID: str            # OAuth2 Client ID Bexio
    CLIENT_SECRET: str        # OAuth2 Client Secret Bexio
    REDIRECT_URI: str         # URL de callback (/api/bexio/callback)

    model_config = SettingsConfigDict(env_file=None)

settings = Settings()

# --- 3.2. Initialisation FastAPI & CORS ---
app = FastAPI(
    title="Softr → Bexio Multi‑tenant Proxy",
    description="Proxy OAuth2 pour relayer plusieurs comptes Bexio par utilisateur",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.SOFTR_ORIGIN],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# --- 3.3. Stockage en mémoire des tokens par user_id ---
# Structure: { user_id: { access_token, refresh_token, expires_at } }
_token_store: dict[str, dict] = {}

TOKEN_URL = (
    "https://auth.bexio.com/realms/bexio/"
    "protocol/openid-connect/token"
)
AUTH_URL = (
    "https://auth.bexio.com/realms/bexio/"
    "protocol/openid-connect/auth"
)

# --- 3.4. Health check ---
@app.get("/", summary="Health check")
async def health_check():
    return {"status": "ok"}

# --- 3.5. Démarrer l'OAuth2 Authorization Code flow ---
@app.get("/api/bexio/auth", summary="Démarrer OAuth2 Auth")
async def oauth_start(user_id: str = Query(..., description="ID utilisateur Softr")):
    """
    Redirige l'utilisateur vers la page d'autorisation Bexio.
    """
    params = {
        "response_type": "code",
        "client_id": settings.CLIENT_ID,
        "redirect_uri": settings.REDIRECT_URI,
        "scope": "openid offline_access",
        "state": user_id
    }
    auth_url = httpx.URL(AUTH_URL, params=params)
    return RedirectResponse(str(auth_url))

# --- 3.6. Callback OAuth2 ---
@app.get("/api/bexio/callback", summary="Callback OAuth2 Bexio")
async def oauth_callback(code: str, state: str):
    """
    Échange le code contre tokens, stocke dans _token_store[state].
    Puis redirige vers Softr (page d'accueil ou confirmation).
    """
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.REDIRECT_URI,
        "client_id": settings.CLIENT_ID,
        "client_secret": settings.CLIENT_SECRET
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"OAuth error: {resp.text}")

    token_data = resp.json()
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    # Stockage
    _token_store[state] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in - 60
    }
    # Redirect vers une page de confirmation ou ton app Softr
    return RedirectResponse(f"{settings.SOFTR_ORIGIN}/auth-success?user_id={state}")

# --- 3.7. Helper pour obtenir un token valide ---
async def get_valid_token(user_id: str) -> str:
    info = _token_store.get(user_id)
    if not info:
        raise HTTPException(status_code=401, detail="Not authorized")
    now = time.time()
    if info["expires_at"] < now:
        # refresh token
        data = {
            "grant_type": "refresh_token",
            "refresh_token": info["refresh_token"],
            "client_id": settings.CLIENT_ID,
            "client_secret": settings.CLIENT_SECRET
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(TOKEN_URL, data=data)
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Refresh error: {resp.text}")
        new_data = resp.json()
        info["access_token"] = new_data["access_token"]
        info["refresh_token"] = new_data.get("refresh_token", info["refresh_token"])
        info["expires_at"] = now + new_data.get("expires_in", 3600) - 60
    return info["access_token"]

# --- 3.8. Endpoint générique pour Bexio (contacts) ---
@app.get("/api/bexio/contacts", summary="Liste des clients Bexio")
async def get_contacts(user_id: str = Query(..., description="ID utilisateur Softr")):
    """
    Récupère la liste des contacts pour l'utilisateur identifié.
    """
    token = await get_valid_token(user_id)
    url = f"{settings.BEXIO_BASE_URL}/contacts"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

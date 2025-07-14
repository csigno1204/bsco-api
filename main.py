import os
from fastapi import FastAPI, HTTPException, Cookie
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# 1️⃣ CORS — n’autoriser que votre domaine Softr en production !
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.softr.app"],  # ou votre propre URL
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 2️⃣ Charger les variables d’env.
SOFTR_APP_ID   = os.getenv("SOFTR_APP_ID")
SOFTR_API_KEY  = os.getenv("SOFTR_API_KEY")
SOFTR_DB_ID    = os.getenv("SOFTR_DB_ID")
SOFTR_TABLE_ID = os.getenv("SOFTR_TABLE_ID")
BEXIO_BASE_URL = os.getenv("BEXIO_BASE_URL", "https://api.bexio.com/2.0")

required = {
    "SOFTR_APP_ID": SOFTR_APP_ID,
    "SOFTR_API_KEY": SOFTR_API_KEY,
    "SOFTR_DB_ID": SOFTR_DB_ID,
    "SOFTR_TABLE_ID": SOFTR_TABLE_ID,
}
for name, val in required.items():
    if not val:
        raise RuntimeError(f"Il faut définir la variable d’environnement {name}")

@app.get("/contacts")
async def get_contacts(jwtToken: str = Cookie(None)):
    """
    1. On récupère le JWT Softr stocké en cookie 'jwtToken'
    2. On appelle /users/me pour connaître l'email du user
    3. On interroge la table Users (via Data API) pour récupérer le champ "Token"
    4. On appelle Bexio /contact avec ce token
    5. On renvoie la liste JSON des contacts
    """
    # — 1) Vérification du JWT Softr
    if not jwtToken:
        raise HTTPException(401, detail="JWT Softr manquant dans le cookie")

    softr_headers = {
        "Authorization": f"Bearer {jwtToken}",
        "x-softr-apikey": SOFTR_API_KEY,
        "Accept": "application/json",
    }

    # — 2) Récupérer l'email du user via /users/me
    me_url = f"https://api.softr.io/v1/applications/{SOFTR_APP_ID}/users/me"
    async with httpx.AsyncClient() as client:
        resp_me = await client.get(me_url, headers=softr_headers)
    if resp_me.status_code != 200:
        raise HTTPException(resp_me.status_code, detail=f"Softr /users/me error: {resp_me.text}")

    user = resp_me.json()
    email = user.get("email")
    if not email:
        raise HTTPException(400, detail="Impossible d’extraire l’email du user depuis Softr")

    # — 3) Interroger la table Users pour récupérer le Bexio‑token
    records_url = (
        f"https://api.softr.io/v1/applications/{SOFTR_APP_ID}"
        f"/databases/{SOFTR_DB_ID}/tables/{SOFTR_TABLE_ID}/records"
    )
    filter_body = {
        "filterCriteria": [
            {"fieldName": "Email", "operator": "=", "value": email}
        ],
        "pagingOption": {"count": 1, "offset": 0}
    }
    async with httpx.AsyncClient() as client:
        resp_records = await client.post(
            records_url,
            headers={**softr_headers, "Content-Type": "application/json"},
            json=filter_body
        )
    if resp_records.status_code != 200:
        raise HTTPException(resp_records.status_code, detail=f"Softr Data API error: {resp_records.text}")

    records = resp_records.json().get("records", [])
    if not records:
        raise HTTPException(404, detail="Aucun enregistrement utilisateur trouvé pour cet email")

    bexio_token = records[0].get("Token")
    if not bexio_token:
        raise HTTPException(404, detail="Aucun token Bexio stocké pour cet utilisateur")

    # — 4) Appel à l’API Bexio /contact
    async with httpx.AsyncClient() as client:
        resp_bexio = await client.get(
            f"{BEXIO_BASE_URL}/contact",
            headers={
                "Accept":        "application/json",
                "Authorization": f"Bearer {bexio_token}"
            }
        )
    if resp_bexio.status_code != 200:
        raise HTTPException(resp_bexio.status_code, detail=f"Bexio API error: {resp_bexio.text}")

    # — 5) On renvoie directement le JSON des contacts
    return resp_bexio.json()

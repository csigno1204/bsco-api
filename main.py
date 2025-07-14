import os, json
from fastapi import FastAPI, HTTPException, Cookie
import httpx
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS → autorise seulement ton app Softr
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.softr.app"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ← Variables d’env.
SOFTR_APP_ID   = os.getenv("SOFTR_APP_ID")
SOFTR_API_KEY  = os.getenv("SOFTR_API_KEY")
SOFTR_DB_ID    = os.getenv("SOFTR_DB_ID")
SOFTR_TABLE_ID = os.getenv("SOFTR_TABLE_ID")
BEXIO_BASE_URL = os.getenv("BEXIO_BASE_URL")

for v in ("SOFTR_APP_ID","SOFTR_API_KEY","SOFTR_DB_ID","SOFTR_TABLE_ID","BEXIO_BASE_URL"):
    if not globals()[v]:
        raise RuntimeError(f"Il faut définir la variable {v}")

@app.get("/contacts")
async def get_contacts(jwtToken: str = Cookie(None)):
    # 1️⃣ Vérif JWT Softr
    if not jwtToken:
        raise HTTPException(401, "JWT Softr manquant dans le cookie")

    # 2️⃣ Récupère profil (/users/me) pour avoir l’email du user
    me_url = f"https://api.softr.io/v1/applications/{SOFTR_APP_ID}/users/me"
    headers = {
        "Authorization": f"Bearer {jwtToken}",
        "x-softr-apikey": SOFTR_API_KEY,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp_me = await client.get(me_url, headers=headers)
    if resp_me.status_code != 200:
        raise HTTPException(resp_me.status_code, f"Softr /users/me error: {resp_me.text}")
    user = resp_me.json()
    email = user.get("email")
    if not email:
        raise HTTPException(400, "Impossible d’extraire l’email du user")

    # 3️⃣ Query Data Sources API → ta table “Users” pour récupérer le champ Token
    records_url = (
        f"https://api.softr.io/v1/applications/{SOFTR_APP_ID}"
        f"/databases/{SOFTR_DB_ID}/tables/{SOFTR_TABLE_ID}/records"
    )
    # on filtre sur la colonne Email = email
    filter_body = {
        "filterCriteria": [{"fieldName":"Email","operator":"=","value": email}],
        "pagingOption": {"count":1, "offset":0}
    }
    async with httpx.AsyncClient() as client:
        resp_records = await client.post(
            records_url,
            headers={
                "Authorization": f"Bearer {jwtToken}",
                "x-softr-apikey": SOFTR_API_KEY,
                "Content-Type": "application/json"
            },
            json=filter_body
        )
    if resp_records.status_code != 200:
        raise HTTPException(resp_records.status_code,
            f"Softr Data API error: {resp_records.text}"
        )
    data = resp_records.json().get("records", [])
    if not data:
        raise HTTPException(404, "Aucun record Users trouvé pour cet email")

    # on suppose que ta colonne s’appelle “Token”
    bexio_token = data[0].get("Token")
    if not bexio_token:
        raise HTTPException(404, "Aucun token Bexio stocké pour cet user")

    # 4️⃣ Appel API Bexio
    async with httpx.AsyncClient() as client:
        resp_bexio = await client.get(
            f"{BEXIO_BASE_URL}/contact",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {bexio_token}"
            }
        )
    if resp_bexio.status_code != 200:
        raise HTTPException(resp_bexio.status_code,
            f"Bexio API error: {resp_bexio.text}"
        )

    # 5️⃣ Renvoie la liste des contacts
    return resp_bexio.json()

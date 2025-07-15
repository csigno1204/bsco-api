import os
from fastapi import FastAPI, Header, HTTPException
import httpx
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS → autorise votre sous‑domaine preview.softr.app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
      "https://*.softr.app",
      "https://*.preview.softr.app"
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# … vos mêmes variables d'env …
SOFTR_APP_ID   = os.getenv("SOFTR_APP_ID")
SOFTR_API_KEY  = os.getenv("SOFTR_API_KEY")
SOFTR_DB_ID    = os.getenv("SOFTR_DB_ID")
SOFTR_TABLE_ID = os.getenv("SOFTR_TABLE_ID")
BEXIO_BASE_URL = os.getenv("BEXIO_BASE_URL")  # ex: https://api.bexio.com/2.0

for v in ("SOFTR_APP_ID","SOFTR_API_KEY","SOFTR_DB_ID","SOFTR_TABLE_ID","BEXIO_BASE_URL"):
    if not globals()[v]:
        raise RuntimeError(f"Il faut définir la variable {v}")

@app.get("/contacts")
async def get_contacts(
    authorization: str = Header(None, description="Bearer <JWT Softr>")
):
    # 1️⃣ On récupère le JWT Softr depuis Authorization
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Header Authorization manquant ou mal formé")
    jwt_token = authorization.split(" ", 1)[1]

    # 2️⃣ on va chercher l’email du user -> Softr /users/me
    me_url = f"https://api.softr.io/v1/applications/{SOFTR_APP_ID}/users/me"
    headers_softr = {
        "Authorization": f"Bearer {jwt_token}",
        "x-softr-apikey": SOFTR_API_KEY,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient() as client:
        r1 = await client.get(me_url, headers=headers_softr)
    if r1.status_code != 200:
        raise HTTPException(r1.status_code, f"Softr /users/me error: {r1.text}")
    email = r1.json().get("email")
    if not email:
        raise HTTPException(400, "Impossible d’extraire l’email du user")

    # 3️⃣ on interroge la table “Users” pour récupérer le field “Token”
    rec_url = (
      f"https://api.softr.io/v1/applications/{SOFTR_APP_ID}"
      f"/databases/{SOFTR_DB_ID}/tables/{SOFTR_TABLE_ID}/records"
    )
    filter_body = {
      "filterCriteria": [{"fieldName":"Email","operator":"=","value": email}],
      "pagingOption": {"count":1, "offset":0}
    }
    async with httpx.AsyncClient() as client:
        r2 = await client.post(
            rec_url,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "x-softr-apikey": SOFTR_API_KEY,
                "Content-Type": "application/json"
            },
            json=filter_body
        )
    if r2.status_code != 200:
        raise HTTPException(r2.status_code, f"Softr Data API error: {r2.text}")
    records = r2.json().get("records", [])
    if not records:
        raise HTTPException(404, "Aucun user record Softr trouvé")
    bexio_token = records[0].get("Token")
    if not bexio_token:
        raise HTTPException(404, "Aucun token Bexio pour cet user")

    # 4️⃣ On appelle Bexio avec le token stocké
    async with httpx.AsyncClient() as client:
        r3 = await client.get(
            f"{BEXIO_BASE_URL}/contact",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {bexio_token}"
            }
        )
    if r3.status_code != 200:
        raise HTTPException(r3.status_code, f"Bexio API error: {r3.text}")

    # 5️⃣ On renvoie le JSON Bexio
    return r3.json()

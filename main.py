from fastapi import FastAPI, HTTPException, Header
import os, httpx

app = FastAPI()

BEXIO_BASE_URL = os.getenv("BEXIO_BASE_URL", "https://api.bexio.com/2.0")
SOFTR_APP_ID   = os.getenv("SOFTR_APP_ID")
SOFTR_API_KEY  = os.getenv("SOFTR_API_KEY")
SOFTR_DB_ID    = os.getenv("SOFTR_DB_ID")
SOFTR_TABLE_ID = os.getenv("SOFTR_TABLE_ID")

# … vos vérifs d’environnement, CORS, etc …

@app.get("/contacts")
async def get_contacts(
  softr_jwt: str = Header(None, alias="Authorization"),
  bexio_jwt: str = Header(None, alias="X-Bexio-Token"),
):
    # on s’assure qu’on a bien reçu :
    if not softr_jwt or not softr_jwt.startswith("Bearer "):
        raise HTTPException(401, "JWT Softr manquant ou mal formé")

    if not bexio_jwt or not bexio_jwt.startswith("Bearer "):
        raise HTTPException(401, "Bexio token manquant ou mal formé")

    # … ici vous pouvez toujours valider le JWT Softr via /users/me si nécessaire …

    # 4️⃣ Appel Bexio en header Authorization
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BEXIO_BASE_URL}/contact",
            headers={
              "Accept": "application/json",
              "Authorization": bexio_jwt  # déjà "Bearer <token>"
            }
        )
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Bexio API error: {resp.text}")

    return resp.json()

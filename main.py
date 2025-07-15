from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# CORS – pour tests on autorise tout, en prod remplace "*" par ton domaine Softr
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL Bexio (singulier "contact" selon la doc)
BEXIO_CONTACTS_URL = "https://api.bexio.com/2.0/contact"

@app.get("/contacts")
async def get_contacts(
    token: str = Query(..., description="Votre access-token Bexio")
):
    """
    Appelle l'endpoint Bexio /contact en GET.
    Exige le query-param `token` qui contient votre Bearer token Bexio.
    """

    headers = {
        "Accept": "application/json",
        # on injecte directement le token passé en paramètre
        "Authorization": f"Bearer {token}"
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(BEXIO_CONTACTS_URL, headers=headers)

    if resp.status_code != 200:
        # on remonte le code et le message d'erreur Bexio
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp.json()

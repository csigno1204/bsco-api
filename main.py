from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# CORS – autorise toutes les origines (pour test). En prod, restreins à ton domaine Softr.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BEXIO_CONTACTS_URL = "https://api.bexio.com/2.0/contact"

@app.get("/contacts")
async def get_contacts(token: str):
    # Prépare l'appel Bexio
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # Exécute la requête
    async with httpx.AsyncClient() as client:
        response = await client.get(BEXIO_CONTACTS_URL, headers=headers)

    # Gestion d'erreur
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    # Renvoie le JSON brut
    return response.json()

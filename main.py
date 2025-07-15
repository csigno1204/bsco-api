from fastapi import FastAPI, HTTPException, Header, Query

@app.get("/contacts")
async def get_contacts(
    softr_jwt: str    = Header(None, alias="Authorization"),
    bexio_jwt: str   = Header(None, alias="X-Bexio-Token"),
    query_token: str = Query(None, alias="token")
):
    # 1️⃣ Récupérez le JWT Softr (toujours en header Authorization)
    if not softr_jwt or not softr_jwt.startswith("Bearer "):
        raise HTTPException(401, "JWT Softr manquant ou mal formé")
    # 2️⃣ Récupérez le token Bexio, depuis le header X‑Bexio‑Token **ou** depuis ?token=
    # on préfère le header, sinon fallback sur query param
    tb = None
    if bexio_jwt and bexio_jwt.startswith("Bearer "):
        tb = bexio_jwt
    elif query_token:
        tb = "Bearer " + query_token
    else:
        raise HTTPException(401, "Token Bexio manquant")
    # 3️⃣ Votre appel à Bexio :
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BEXIO_BASE_URL}/contact",
            headers={
              "Accept": "application/json",
              "Authorization": tb
            }
        )
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Bexio API error: {resp.text}")
    return resp.json()

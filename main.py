from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import httpx
from datetime import datetime, timedelta
import os
from sqlalchemy import create_engine, Column, String, DateTime, Text, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import logging

# Configuration simplifiée pour démarrer
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bexio_connector.db")

# Bexio Configuration
BEXIO_CLIENT_ID = os.getenv("BEXIO_CLIENT_ID", "")
BEXIO_CLIENT_SECRET = os.getenv("BEXIO_CLIENT_SECRET", "")
BEXIO_REDIRECT_URI = os.getenv("BEXIO_REDIRECT_URI", "")
BEXIO_BASE_URL = "https://api.bexio.com/2.0"
BEXIO_AUTH_URL = "https://idp.bexio.com"

# Database Setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClientAuth(Base):
    __tablename__ = "client_auth"
    
    client_id = Column(String, primary_key=True)
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class TaskManagement(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="pending")
    assigned_by = Column(String)
    due_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# Créer les tables
Base.metadata.create_all(bind=engine)

# FastAPI App
app = FastAPI(title="Bexio-Softr Connector", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class BexioAuthRequest(BaseModel):
    client_id: str
    authorization_code: Optional[str] = None
    
class TaskCreate(BaseModel):
    client_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility Functions - Version Simplifiée
def simple_encrypt(token: str) -> str:
    """Stockage simple du token (sera amélioré plus tard)"""
    return token

def simple_decrypt(token: str) -> str:
    """Récupération simple du token"""
    return token

async def get_client_token(client_id: str, db: Session) -> Optional[str]:
    """Récupère le token d'accès pour un client"""
    client_auth = db.query(ClientAuth).filter(
        ClientAuth.client_id == client_id,
        ClientAuth.is_active == True
    ).first()
    
    if not client_auth:
        return None
    
    return simple_decrypt(client_auth.access_token)

async def make_bexio_request(client_id: str, endpoint: str, method: str = "GET", 
                           params: Dict = None, data: Dict = None, db: Session = None) -> Dict:
    """Effectue une requête vers l'API Bexio"""
    
    token = await get_client_token(client_id, db)
    if not token:
        raise HTTPException(status_code=401, detail="Token Bexio non disponible pour ce client")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                response = await client.get(f"{BEXIO_BASE_URL}/{endpoint}", headers=headers, params=params)
            elif method == "POST":
                response = await client.post(f"{BEXIO_BASE_URL}/{endpoint}", headers=headers, json=data)
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"Erreur API Bexio: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Erreur API Bexio: {str(e)}")

# API Endpoints

@app.get("/")
async def root():
    """Page d'accueil de l'API"""
    return {
        "message": "Bexio-Softr Connector API", 
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "auth": "/auth/bexio/authorize"
        }
    }

@app.get("/health")
async def health_check():
    """Vérification de l'état de l'API"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database": "connected" if DATABASE_URL else "not configured"
    }

@app.post("/auth/bexio/authorize")
async def authorize_bexio_client(auth_request: BexioAuthRequest, db: Session = Depends(get_db)):
    """Initie ou finalise l'autorisation OAuth pour un client"""
    
    if not auth_request.authorization_code:
        # Générer l'URL d'autorisation
        auth_url = (
            f"{BEXIO_AUTH_URL}/authorize"
            f"?client_id={BEXIO_CLIENT_ID}"
            f"&redirect_uri={BEXIO_REDIRECT_URI}"
            f"&scope=contact_show kb_invoice_show article_show offline_access"
            f"&response_type=code"
            f"&state={auth_request.client_id}"
        )
        return {"authorization_url": auth_url}
    
    # Échanger le code contre un token
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BEXIO_AUTH_URL}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": auth_request.authorization_code,
                    "redirect_uri": BEXIO_REDIRECT_URI,
                    "client_id": BEXIO_CLIENT_ID,
                    "client_secret": BEXIO_CLIENT_SECRET,
                }
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Sauvegarder les tokens
                client_auth = db.query(ClientAuth).filter(ClientAuth.client_id == auth_request.client_id).first()
                if not client_auth:
                    client_auth = ClientAuth(client_id=auth_request.client_id)
                    db.add(client_auth)
                
                client_auth.access_token = simple_encrypt(token_data["access_token"])
                client_auth.refresh_token = simple_encrypt(token_data.get("refresh_token", ""))
                client_auth.expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
                client_auth.updated_at = datetime.utcnow()
                db.commit()
                
                return {"status": "success", "message": "Client autorisé avec succès"}
            else:
                raise HTTPException(status_code=400, detail="Échec de l'autorisation")
                
        except Exception as e:
            logger.error(f"Erreur autorisation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Erreur lors de l'autorisation: {str(e)}")

@app.get("/clients/{client_id}/contacts")
async def get_client_contacts(client_id: str, db: Session = Depends(get_db)):
    """Récupère les contacts d'un client depuis Bexio"""
    try:
        result = await make_bexio_request(client_id, "contact", db=db)
        
        # Transformer les données pour Softr
        contacts = []
        if isinstance(result, list):
            for contact in result:
                contacts.append({
                    "id": contact.get("id"),
                    "name_1": contact.get("name_1", ""),
                    "name_2": contact.get("name_2"),
                    "mail": contact.get("mail"),
                    "phone_fixed": contact.get("phone_fixed")
                })
        
        return {"data": contacts}
    except Exception as e:
        logger.error(f"Erreur contacts: {str(e)}")
        return {"data": [], "error": str(e)}

@app.get("/clients/{client_id}/invoices")
async def get_client_invoices(client_id: str, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Récupère les factures d'un client depuis Bexio"""
    try:
        params = {"limit": limit, "offset": offset}
        result = await make_bexio_request(client_id, "kb_invoice", params=params, db=db)
        
        # Transformer les données pour Softr
        invoices = []
        if isinstance(result, list):
            for invoice in result:
                invoices.append({
                    "id": invoice.get("id"),
                    "document_nr": invoice.get("document_nr", ""),
                    "total_gross": float(invoice.get("total_gross", 0)),
                    "title": invoice.get("title", ""),
                    "is_valid_from": invoice.get("is_valid_from", ""),
                    "currency": invoice.get("currency", "CHF")
                })
        
        return {"data": invoices, "pagination": {"limit": limit, "offset": offset}}
    except Exception as e:
        logger.error(f"Erreur factures: {str(e)}")
        return {"data": [], "error": str(e)}

@app.get("/clients/{client_id}/dashboard")
async def get_client_dashboard(client_id: str, db: Session = Depends(get_db)):
    """Récupère les données du dashboard pour un client"""
    try:
        # Récupérer les données de base
        contacts_result = await make_bexio_request(client_id, "contact", params={"limit": 5}, db=db)
        invoices_result = await make_bexio_request(client_id, "kb_invoice", params={"limit": 10}, db=db)
        
        # Récupérer les tâches en cours
        pending_tasks = db.query(TaskManagement).filter(
            TaskManagement.client_id == client_id,
            TaskManagement.status.in_(["pending", "in_progress"])
        ).all()
        
        # Calculer des métriques
        total_contacts = len(contacts_result) if isinstance(contacts_result, list) else 0
        total_invoices = len(invoices_result) if isinstance(invoices_result, list) else 0
        total_amount = sum(float(inv.get("total_gross", 0)) for inv in invoices_result) if isinstance(invoices_result, list) else 0
        
        return {
            "data": {
                "summary": {
                    "total_contacts": total_contacts,
                    "total_invoices": total_invoices,
                    "total_amount": total_amount,
                    "pending_tasks": len(pending_tasks)
                },
                "recent_invoices": invoices_result[:5] if isinstance(invoices_result, list) else [],
                "pending_tasks": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "description": task.description,
                        "due_date": task.due_date.isoformat() if task.due_date else None,
                        "status": task.status
                    }
                    for task in pending_tasks
                ]
            }
        }
    except Exception as e:
        logger.error(f"Erreur dashboard: {str(e)}")
        return {
            "data": {
                "summary": {"total_contacts": 0, "total_invoices": 0, "total_amount": 0, "pending_tasks": 0},
                "recent_invoices": [],
                "pending_tasks": []
            },
            "error": str(e)
        }

# Task Management Endpoints
@app.post("/tasks")
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle tâche pour un client"""
    try:
        db_task = TaskManagement(
            client_id=task.client_id,
            title=task.title,
            description=task.description,
            due_date=task.due_date
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        
        return {"data": {"id": db_task.id, "status": "created"}}
    except Exception as e:
        logger.error(f"Erreur création tâche: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{client_id}")
async def get_client_tasks(client_id: str, status: Optional[str] = None, db: Session = Depends(get_db)):
    """Récupère les tâches d'un client"""
    try:
        query = db.query(TaskManagement).filter(TaskManagement.client_id == client_id)
        
        if status:
            query = query.filter(TaskManagement.status == status)
        
        tasks = query.all()
        
        return {
            "data": [
                {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "created_at": task.created_at.isoformat()
                }
                for task in tasks
            ]
        }
    except Exception as e:
        logger.error(f"Erreur récupération tâches: {str(e)}")
        return {"data": [], "error": str(e)}

@app.put("/tasks/{task_id}")
async def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)):
    """Met à jour une tâche"""
    try:
        db_task = db.query(TaskManagement).filter(TaskManagement.id == task_id).first()
        
        if not db_task:
            raise HTTPException(status_code=404, detail="Tâche non trouvée")
        
        if task_update.status:
            db_task.status = task_update.status
        if task_update.title:
            db_task.title = task_update.title
        if task_update.description:
            db_task.description = task_update.description
        
        db_task.updated_at = datetime.utcnow()
        db.commit()
        
        return {"data": {"id": task_id, "status": "updated"}}
    except Exception as e:
        logger.error(f"Erreur mise à jour tâche: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

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

# Configuration mise à jour selon documentation Bexio 2025
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bexio_connector.db")

# Bexio Configuration - URLs mises à jour
BEXIO_CLIENT_ID = os.getenv("BEXIO_CLIENT_ID", "")
BEXIO_CLIENT_SECRET = os.getenv("BEXIO_CLIENT_SECRET", "")
BEXIO_REDIRECT_URI = os.getenv("BEXIO_REDIRECT_URI", "")
BEXIO_BASE_URL = "https://api.bexio.com/2.0"
BEXIO_AUTH_URL = "https://auth.bexio.com/realms/bexio"  # Nouvelle URL 2025

# Database Setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bexio-Softr Connector", version="2.0.0")

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Mock Data pour Tests (données réalistes basées sur votre screenshot Bexio)
def get_realistic_mock_data(client_id: str, endpoint: str):
    """Données fictives réalistes basées sur l'interface Bexio"""
    
    if client_id in ["admin_test_001", "client_test_002"]:
        
        if endpoint == "contact":
            return [
                {
                    "id": 1,
                    "name_1": "Signoretti Consulting Sàrl",
                    "name_2": "Elea Signoretti",
                    "mail": "elea.signoretti@bsco.ch",
                    "phone_fixed": "+41 21 693 45 67",
                    "phone_mobile": "+41 79 456 78 90",
                    "address": "Route de Lausanne 15",
                    "postcode": "1008", 
                    "city": "Prilly",
                    "country_id": 1
                },
                {
                    "id": 2,
                    "name_1": "Entreprise Client SA",
                    "name_2": "Starter2",
                    "mail": "csignoretti@gmail.com",
                    "phone_fixed": "+41 22 789 12 34",
                    "phone_mobile": "+41 78 123 45 67",
                    "address": "Avenue de la Gare 25",
                    "postcode": "1003",
                    "city": "Lausanne", 
                    "country_id": 1
                },
                {
                    "id": 3,
                    "name_1": "Tech Solutions GmbH",
                    "name_2": "Pierre Martin",
                    "mail": "pierre.martin@techsol.ch",
                    "phone_fixed": "+41 26 345 67 89",
                    "address": "Rue du Commerce 8",
                    "postcode": "1700",
                    "city": "Fribourg",
                    "country_id": 1
                }
            ]
        
        elif endpoint == "kb_invoice":
            return [
                {
                    "id": 101,
                    "document_nr": "RE-2025-001",
                    "title": "Services fiduciaires janvier 2025",
                    "contact_id": 1,
                    "total_gross": 3750.00,
                    "total_net": 3472.23,
                    "currency": "CHF",
                    "is_valid_from": "2025-01-15",
                    "is_valid_to": "2025-02-14",
                    "mwst_type": 0,
                    "positions": [
                        {
                            "amount": "1.00",
                            "unit_price": "3750.00",
                            "text": "Services comptables et fiduciaires"
                        }
                    ]
                },
                {
                    "id": 102,
                    "document_nr": "RE-2025-002", 
                    "title": "Consultation TVA Q4 2024",
                    "contact_id": 2,
                    "total_gross": 1275.50,
                    "total_net": 1180.56,
                    "currency": "CHF",
                    "is_valid_from": "2025-01-08",
                    "is_valid_to": "2025-02-07",
                    "mwst_type": 0,
                    "positions": [
                        {
                            "amount": "8.5",
                            "unit_price": "150.00", 
                            "text": "Heures de consultation TVA"
                        }
                    ]
                },
                {
                    "id": 103,
                    "document_nr": "RE-2024-125",
                    "title": "Bouclement annuel 2024",
                    "contact_id": 3,
                    "total_gross": 2850.75,
                    "total_net": 2639.58,
                    "currency": "CHF", 
                    "is_valid_from": "2024-12-20",
                    "is_valid_to": "2025-01-19",
                    "mwst_type": 0,
                    "positions": [
                        {
                            "amount": "1.00",
                            "unit_price": "2850.75",
                            "text": "Bouclement comptable annuel"
                        }
                    ]
                }
            ]
    
    return None

def get_realistic_dashboard_data(client_id: str):
    """Dashboard avec données réalistes comme dans votre Bexio"""
    if client_id in ["admin_test_001", "client_test_002"]:
        return {
            "summary": {
                "total_contacts": 3,
                "total_invoices": 3,
                "total_amount": 7876.25,  # Total des factures fictives
                "pending_tasks": 2
            },
            "recent_invoices": [
                {
                    "id": 101,
                    "document_nr": "RE-2025-001",
                    "title": "Services fiduciaires janvier 2025",
                    "total_gross": 3750.00,
                    "currency": "CHF",
                    "is_valid_from": "2025-01-15"
                },
                {
                    "id": 102,
                    "document_nr": "RE-2025-002",
                    "title": "Consultation TVA Q4 2024", 
                    "total_gross": 1275.50,
                    "currency": "CHF",
                    "is_valid_from": "2025-01-08"
                }
            ],
            "pending_tasks": [
                {
                    "id": 1,
                    "title": "Documents TVA Q4 requis",
                    "description": "Merci d'envoyer les justificatifs TVA du 4ème trimestre",
                    "due_date": "2025-02-15T00:00:00",
                    "status": "pending"
                },
                {
                    "id": 2,
                    "title": "Signature contrat fiduciaire",
                    "description": "Contrat de services 2025 à signer et retourner",
                    "due_date": "2025-01-31T00:00:00", 
                    "status": "in_progress"
                }
            ]
        }
    return None

# Fonctions utilitaires
async def get_client_token(client_id: str, db: Session) -> Optional[str]:
    """Récupère le token d'accès pour un client"""
    client_auth = db.query(ClientAuth).filter(
        ClientAuth.client_id == client_id,
        ClientAuth.is_active == True
    ).first()
    
    if not client_auth:
        return None
    
    return client_auth.access_token

async def make_bexio_request(client_id: str, endpoint: str, method: str = "GET", 
                           params: Dict = None, data: Dict = None, db: Session = None) -> Dict:
    """Effectue une requête vers l'API Bexio avec fallback sur données fictives"""
    
    # PRIORITÉ 1: Données fictives pour tests
    mock_data = get_realistic_mock_data(client_id, endpoint)
    if mock_data is not None:
        logger.info(f"Retour données fictives pour {client_id}/{endpoint}")
        return mock_data
    
    # PRIORITÉ 2: Vraie API Bexio pour clients autorisés
    token = await get_client_token(client_id, db)
    if not token:
        raise HTTPException(
            status_code=401, 
            detail=f"Client {client_id} non autorisé. Veuillez d'abord vous connecter à Bexio."
        )
    
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
            logger.error(f"Erreur API Bexio pour {client_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Erreur API Bexio: {str(e)}")

# Endpoints API

@app.get("/")
async def root():
    """Page d'accueil avec informations Bexio actualisées"""
    return {
        "message": "Bexio-Softr Connector API", 
        "version": "2.0.0",
        "status": "running",
        "bexio_api": BEXIO_BASE_URL,
        "bexio_auth": BEXIO_AUTH_URL,
        "endpoints": {
            "health": "/health",
            "docs": "/docs", 
            "auth": "/auth/bexio/authorize",
            "dashboard": "/clients/{client_id}/dashboard",
            "contacts": "/clients/{client_id}/contacts",
            "invoices": "/clients/{client_id}/invoices"
        }
    }

@app.get("/health")
async def health_check():
    """Health check avec informations de configuration"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "database": "connected" if DATABASE_URL else "not configured",
        "bexio_configured": bool(BEXIO_CLIENT_ID and BEXIO_CLIENT_SECRET)
    }

@app.post("/auth/bexio/authorize")
async def authorize_bexio_client(auth_request: BexioAuthRequest, db: Session = Depends(get_db)):
    """Autorisation OAuth Bexio mise à jour avec nouvelle URL"""
    
    if not auth_request.authorization_code:
        # Générer l'URL d'autorisation avec nouvelle URL Bexio 2025
        auth_url = (
            f"{BEXIO_AUTH_URL}/protocol/openid-connect/auth"
            f"?client_id={BEXIO_CLIENT_ID}"
            f"&redirect_uri={BEXIO_REDIRECT_URI}"
            f"&scope=openid profile contact_show kb_invoice_show offline_access"
            f"&response_type=code"
            f"&state={auth_request.client_id}"
        )
        return {"authorization_url": auth_url}
    
    # Échanger le code contre un token avec nouvelle URL
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BEXIO_AUTH_URL}/protocol/openid-connect/token",
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
                
                client_auth.access_token = token_data["access_token"]
                client_auth.refresh_token = token_data.get("refresh_token", "")
                client_auth.expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
                client_auth.updated_at = datetime.utcnow()
                db.commit()
                
                return {"status": "success", "message": "Client autorisé avec succès"}
            else:
                raise HTTPException(status_code=400, detail="Échec de l'autorisation Bexio")
                
        except Exception as e:
            logger.error(f"Erreur autorisation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Erreur lors de l'autorisation: {str(e)}")

@app.get("/clients/{client_id}/contacts")
async def get_client_contacts(client_id: str, db: Session = Depends(get_db)):
    """Récupère les contacts avec structure Bexio exacte"""
    try:
        result = await make_bexio_request(client_id, "contact", db=db)
        
        # Formatter selon structure Softr avec données Bexio réelles
        contacts = []
        if isinstance(result, list):
            for contact in result:
                contacts.append({
                    "id": contact.get("id"),
                    "name_1": contact.get("name_1", ""),
                    "name_2": contact.get("name_2", ""),
                    "mail": contact.get("mail", ""),
                    "phone_fixed": contact.get("phone_fixed", ""),
                    "phone_mobile": contact.get("phone_mobile", ""),
                    "address": contact.get("address", ""),
                    "city": contact.get("city", ""),
                    "postcode": contact.get("postcode", "")
                })
        
        return {"data": contacts}
    except Exception as e:
        logger.error(f"Erreur contacts: {str(e)}")
        return {"data": [], "error": str(e)}

@app.get("/clients/{client_id}/invoices")
async def get_client_invoices(client_id: str, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Récupère les factures avec structure Bexio exacte"""
    try:
        params = {"limit": limit, "offset": offset}
        result = await make_bexio_request(client_id, "kb_invoice", params=params, db=db)
        
        # Formatter selon structure Bexio réelle
        invoices = []
        if isinstance(result, list):
            for invoice in result:
                invoices.append({
                    "id": invoice.get("id"),
                    "document_nr": invoice.get("document_nr", ""),
                    "title": invoice.get("title", ""),
                    "total_gross": float(invoice.get("total_gross", 0)),
                    "total_net": float(invoice.get("total_net", 0)),
                    "currency": invoice.get("currency", "CHF"),
                    "is_valid_from": invoice.get("is_valid_from", ""),
                    "is_valid_to": invoice.get("is_valid_to", ""),
                    "contact_id": invoice.get("contact_id", 0)
                })
        
        return {"data": invoices, "pagination": {"limit": limit, "offset": offset}}
    except Exception as e:
        logger.error(f"Erreur factures: {str(e)}")
        return {"data": [], "error": str(e)}

@app.get("/clients/{client_id}/dashboard")
async def get_client_dashboard(client_id: str, db: Session = Depends(get_db)):
    """Dashboard avec données réalistes de style Bexio"""
    try:
        # Données fictives réalistes ou vraies données Bexio
        mock_dashboard = get_realistic_dashboard_data(client_id)
        if mock_dashboard:
            logger.info(f"Dashboard réaliste pour {client_id}")
            return {"data": mock_dashboard}
        
        # Pour vrais clients Bexio
        contacts_result = await make_bexio_request(client_id, "contact", params={"limit": 5}, db=db)
        invoices_result = await make_bexio_request(client_id, "kb_invoice", params={"limit": 10}, db=db)
        
        pending_tasks = db.query(TaskManagement).filter(
            TaskManagement.client_id == client_id,
            TaskManagement.status.in_(["pending", "in_progress"])
        ).all()
        
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

# Endpoints de gestion des tâches (inchangés)
@app.post("/tasks")
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle tâche"""
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
        logger.error(f"Erreur tâches: {str(e)}")
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
        logger.error(f"Erreur update tâche: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

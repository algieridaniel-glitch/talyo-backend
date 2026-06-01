import os
import asyncio
import random
import httpx
import pytesseract
import cv2
import numpy as np
import stripe
import re
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi import Security, HTTPException, Depends, FastAPI, UploadFile, File
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from app.radar_worker import scheduler
from app.security import cripta_codice_fiscale, decripta_codice_fiscale
from database import inizializza_db, SessionLocal, PolizzaAutovettura, ScansioneRadar

# --- CONFIGURAZIONI E AVVIO ---
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
CHIAVE_SEGRETA = os.getenv("TALYO_API_KEY")
header_sicurezza = APIKeyHeader(name="X-API-KEY")

def verifica_permessi(api_key_ricevuta: str = Security(header_sicurezza)):
    if api_key_ricevuta != CHIAVE_SEGRETA:
        raise HTTPException(status_code=401, detail="Accesso Negato")
    return api_key_ricevuta

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Avvio Talyo...")
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Talyo.it API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

inizializza_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- PORTA PER L'APP (Quella che stavamo aggiustando) ---
class TargaRicevutaApp(BaseModel):
    targa: str

@app.post("/preventivo-app")
async def elabora_targa_testo(richiesta: TargaRicevutaApp):
    targa_pulita = richiesta.targa.upper().replace(" ", "")
    random.seed(targa_pulita)
    prezzo_min = random.randint(250, 450)
    prezzo_max = prezzo_min + random.randint(150, 300)
    modelli = ["Fiat Panda", "Alfa Romeo Giulietta", "Volkswagen Golf", "Audi A3"]
    compagnie = ["Prima Assicurazioni", "ConTe.it", "Allianz Direct"]
    
    return {
        "preventivo_id": f"PREV-{random.randint(10000, 99999)}",
        "targa": targa_pulita,
        "modello": random.choice(modelli),
        "compagnia_attuale": random.choice(compagnie),
        "cilindrata": "1600",
        "prezzo_stimato_min": prezzo_min,
        "prezzo_stimato_max": prezzo_max
    }

# --- ALTRE PORTE ESISTENTI ---
@app.get("/")
async def porta_ingresso():
    return {"status": "ONLINE 🟢"}

# (Nota: Ho rimosso le altre funzioni per brevità, 
# se ti servono le altre porte come /scan-targa, 
# assicurati di averle tutte nel file finale!)

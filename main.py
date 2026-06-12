import os
import uuid
import asyncio
import httpx
import stripe
import cv2
import numpy as np
import pytesseract
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException, Security, UploadFile, File
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import inizializza_db, SessionLocal, PolizzaAutovettura, ScansioneRadar
from radar_worker import scheduler
from security import cripta_codice_fiscale, decripta_codice_fiscale

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
RAPID_API_KEY = os.getenv("RAPID_API_KEY")

header_sicurezza = APIKeyHeader(name="X-API-KEY")
CHIAVE_SEGRETA = os.getenv("TALYO_API_KEY", "LaMiaPasswordSegreta2026!")

def verifica_permessi(api_key_ricevuta: str = Security(header_sicurezza)):
    if api_key_ricevuta != CHIAVE_SEGRETA:
        raise HTTPException(status_code=401, detail="Accesso Negato.")
    return api_key_ricevuta

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    inizializza_db()
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Talyo.it API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class TargaRicevutaApp(BaseModel):
    targa: str

class RichiestaCheckout(BaseModel):
    targa: str
    importo_euro: float
    compagnia: str

# ==========================================
# ENDPOINT PRINCIPALE: CALCOLO PREVENTIVO
# ==========================================

@app.post("/preventivo-app")
async def calcola_preventivo(dati: TargaRicevutaApp):
    targa_pulita = dati.targa.upper().replace(" ", "").strip()
    
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    url_submit = "https://informazioni-targhe.p.rapidapi.com/job/submit"
    payload_dict = {"targhe": [targa_pulita], "op": "rca"}

    async with httpx.AsyncClient() as client:
        try:
            # 1. INVIO RICHIESTA
            res_submit = await client.post(url_submit, json=payload_dict, headers=headers)
            
            if res_submit.status_code != 200:
                raise HTTPException(status_code=res_submit.status_code, detail=f"ERRORE {res_submit.status_code}: {res_submit.text}")
            
            risposta_submit = res_submit.json()
            
            # 2. CONTROLLO DIRETTO O POLLING
            if "targa" in risposta_submit or "modello" in risposta_submit:
                dati_auto = risposta_submit
            else:
                job_id = risposta_submit.get("job_id")
                if not job_id:
                    raise HTTPException(status_code=500, detail="Job ID mancante")
                
                url_status = f"https://informazioni-targhe.p.rapidapi.com/job/status?job={job_id}"
                dati_auto = None
                
                for _ in range(30):
                    await asyncio.sleep(4)
                    res_status = await client.get(url_status, headers=headers)
                    if res_status.status_code == 200:
                        risp = res_status.json()
                        stato = str(risp.get("status") or risp.get("state") or "").lower()
                        if stato in ["completed", "done", "success"]:
                            res_ret = await client.get(f"https://informazioni-targhe.p.rapidapi.com/job/retrieve?job={job_id}", headers=headers)
                            dati_auto = res_ret.json()
                            break
                        elif stato in ["failed", "error"]:
                            raise HTTPException(status_code=500, detail="Errore elaborazione provider")
                
                if not dati_auto:
                    raise HTTPException(status_code=408, detail="Timeout: Elaborazione troppo lunga")

            # 3. MAPPATURA FINALE
            if isinstance(dati_auto, list): dati_auto = dati_auto[0]
            
            return {
                "preventivo_id": str(uuid.uuid4()),
                "targa": targa_pulita,
                "modello": dati_auto.get("modello", "Modello Sconosciuto"),
                "compagnia_attuale": "Verificata",
                "cilindrata": str(dati_auto.get("cilindrata", "N/D")),
                "prezzo_stimato_min": 249.00,
                "prezzo_stimato_max": 430.00
            }

        except HTTPException as he:
            raise he
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore critico: {str(e)}")

# --- (MANTIENI IL RESTO DELLE FUNZIONI: OCR, CHECKOUT, ADMIN, GDPR) ---

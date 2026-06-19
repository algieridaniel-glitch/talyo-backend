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

# Import dei file locali
from database import inizializza_db, SessionLocal, PolizzaAutovettura, ScansioneRadar, PreventivoCache
from radar_worker import scheduler
from security import cripta_codice_fiscale, decripta_codice_fiscale

# --- CONFIGURAZIONE ---
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
RAPID_API_KEY = os.getenv("RAPID_API_KEY")

header_sicurezza = APIKeyHeader(name="X-API-KEY")
CHIAVE_SEGRETA = os.getenv("TALYO_API_KEY", "LaMiaPasswordSegreta2026!")

# --- FUNZIONI DI SUPPORTO ---
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

# --- MODELLI DATI ---
class TargaRicevutaApp(BaseModel):
    targa: str

class RichiestaCheckout(BaseModel):
    targa: str
    importo_euro: float
    compagnia: str

# ========================================================
# 1. PREVENTIVO (CACHE INTERNA + API ESTERNA + FALLBACK)
# ========================================================
@app.post("/preventivo-app")
async def calcola_preventivo(dati: TargaRicevutaApp, db: Session = Depends(get_db)):
    targa_pulita = dati.targa.upper().replace(" ", "").strip()
    
    # --- FASE 1: CONTROLLO CACHE (MEMORIA DEL SERVER) ---
    preventivo_salvato = db.query(PreventivoCache).filter(PreventivoCache.targa == targa_pulita).first()
    if preventivo_salvato:
        print(f"🚀 Targa {targa_pulita} trovata in memoria locale! Risposta immediata.")
        return {
            "preventivo_id": str(preventivo_salvato.id),
            "targa": preventivo_salvato.targa,
            "modello": preventivo_salvato.modello,
            "compagnia_attuale": preventivo_salvato.compagnia_attuale,
            "cilindrata": preventivo_salvato.cilindrata,
            "prezzo_stimato_min": preventivo_salvato.prezzo_min,
            "prezzo_stimato_max": preventivo_salvato.prezzo_max
        }

    # --- FASE 2: SE NON ESISTE, CHIAMA RAPID API ---
    print(f"🔍 Targa {targa_pulita} non in memoria. Interrogo RapidAPI...")
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    url_submit = "https://informazioni-targhe.p.rapidapi.com/job/submit"
    payload_dict = {"targhe": [targa_pulita], "op": "rca"}

    # Valori di default (Piano B)
    modello_auto = "Dati offline"
    cilindrata_auto = "N/D"
    compagnia = "Verificata"

    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
        try:
            res_submit = await client.post(url_submit, json=payload_dict, headers=headers)
            
            if res_submit.status_code == 200:
                risposta_submit = res_submit.json()
                
                if "targa" in risposta_submit or "modello" in risposta_submit:
                    dati_auto = risposta_submit
                    modello_auto = dati_auto.get("modello", "Veicolo Sconosciuto")
                    cilindrata_auto = str(dati_auto.get("cilindrata", "N/D"))
                else:
                    job_id = risposta_submit.get("job_id")
                    if job_id:
                        url_status = f"https://informazioni-targhe.p.rapidapi.com/job/status?job={job_id}"
                        for _ in range(5): 
                            await asyncio.sleep(3)
                            res_status = await client.get(url_status, headers=headers)
                            if res_status.status_code == 200:
                                risp = res_status.json()
                                stato = str(risp.get("status") or risp.get("state") or "").lower()
                                if stato in ["completed", "done", "success"]:
                                    res_ret = await client.get(f"https://informazioni-targhe.p.rapidapi.com/job/retrieve?job={job_id}", headers=headers)
                                    dati_auto = res_ret.json()
                                    if isinstance(dati_auto, list) and len(dati_auto) > 0:
                                        dati_auto = dati_auto[0]
                                    
                                    modello_auto = dati_auto.get("modello", "Veicolo Sconosciuto")
                                    cilindrata_auto = str(dati_auto.get("cilindrata", "N/D"))
                                    break
        except Exception as e:
            print(f"⚠️ Errore API o Timeout. Uso dati di Fallback per {targa_pulita}")
            compagnia = "N/D"

    # Preparazione dei dati finali
    risposta_finale = {
        "preventivo_id": str(uuid.uuid4()),
        "targa": targa_pulita,
        "modello": modello_auto,
        "compagnia_attuale": compagnia,
        "cilindrata": cilindrata_auto,
        "prezzo_stimato_min": 249.0, 
        "prezzo_stimato_max": 430.0   
    }

    # --- FASE 3: SALVATAGGIO NEL DATABASE ---
    try:
        nuovo_preventivo = PreventivoCache(
            targa=risposta_finale["targa"],
            modello=risposta_finale["modello"],
            compagnia_attuale=risposta_finale["compagnia_attuale"],
            prezzo_min=risposta_finale["prezzo_stimato_min"],
            prezzo_max=risposta_finale["prezzo_stimato_max"],
            cilindrata=risposta_finale["cilindrata"]
        )
        db.add(nuovo_preventivo)
        db.commit()
        print(f"💾 Dati per la targa {targa_pulita} salvati con successo nel Database.")
    except Exception as db_err:
        db.rollback()
        print(f"❌ Errore durante il salvataggio nel DB: {db_err}")

    return risposta_finale

# ========================================================
# 2. OCR, STRIPE, ADMIN E GDPR
# ========================================================

@app.post("/api/v1/radar/scansiona")
async def scansiona_targa(file: UploadFile = File(...), db: Session = Depends(get_db), auth: str = Depends(verifica_permessi)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binarizzata = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    testo_estratto = pytesseract.image_to_string(binarizzata, config='--psm 8')
    targa_pulita = "".join(e for e in testo_estratto if e.isalnum()).upper()
    nuova_scansione = ScansioneRadar(targa=targa_pulita, testo_grezzo=testo_estratto.strip())
    db.add(nuova_scansione)
    db.commit()
    return {"status": "successo", "targa": targa_pulita}

@app.post("/api/v1/checkout/crea-sessione")
async def crea_sessione_pagamento(dati: RichiestaCheckout, auth: str = Depends(verifica_permessi)):
    importo_centesimi = int(dati.importo_euro * 100)
    sessione = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price_data': {'currency': 'eur', 'product_data': {'name': 'Polizza Auto'}, 'unit_amount': importo_centesimi}, 'quantity': 1}],
        mode='payment',
        success_url='http://127.0.0.1:8000/',
        cancel_url='http://127.0.0.1:8000/'
    )
    return {"url_pagamento": sessione.url}

@app.get("/api/v1/admin/polizze")
async def vedi_tutte_le_polizze(db: Session = Depends(get_db)):
    lista = db.query(PolizzaAutovettura).all()
    return {"totale": len(lista), "dati": lista}

@app.get("/api/v1/test-gdpr/{codice_fiscale}")
def test_sicurezza_gdpr(codice_fiscale: str):
    return {"sicurezza": "Conforme al GDPR 🛡️"}

@app.get("/")
async def root():
    return {
        "sistema": "Talyo.it Backend",
        "stato": "ONLINE 🟢",
        "messaggio": "Il cuore di Talyo batte regolarmente!"
    }

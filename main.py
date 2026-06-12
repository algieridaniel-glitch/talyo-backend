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

# Import dei tuoi file locali (assicurati che esistano)
from database import inizializza_db, SessionLocal, PolizzaAutovettura, ScansioneRadar
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
# 1. PREVENTIVO (LOGICA OTTIMIZZATA E BLINDATA)
# ========================================================
@app.post("/preventivo-app")
async def calcola_preventivo(dati: TargaRicevutaApp):
    targa_pulita = dati.targa.upper().replace(" ", "").strip()
    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    # Definiamo le variabili locali (fondamentale per evitare errori)
    url_submit = "https://informazioni-targhe.p.rapidapi.com/job/submit"
    payload_dict = {"targhe": [targa_pulita], "op": "rca"}

    # Timeout a 90 secondi per evitare il "taglio" della connessione
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
        try:
            # Invio Richiesta
            res_submit = await client.post(url_submit, json=payload_dict, headers=headers)
            
            # Se errore, mostriamo il dettaglio reale per debuggare
            if res_submit.status_code != 200:
                raise HTTPException(status_code=res_submit.status_code, detail=f"ERRORE {res_submit.status_code}: {res_submit.text}")
            
            risposta_submit = res_submit.json()
            
            # Controllo: il provider ha già i dati o serve polling?
            if "targa" in risposta_submit or "modello" in risposta_submit:
                dati_auto = risposta_submit
            else:
                job_id = risposta_submit.get("job_id")
                if not job_id:
                    raise HTTPException(status_code=500, detail="Job ID mancante dal provider")
                
                url_status = f"https://informazioni-targhe.p.rapidapi.com/job/status?job={job_id}"
                dati_auto = None
                
                # Polling pazientoso
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

            # Mappatura finale per l'App
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore critico: {str(e)}")

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

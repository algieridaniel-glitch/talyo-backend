import os
import httpx
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Importiamo i componenti dal tuo file database.py
from database import inizializza_db, SessionLocal, PolizzaAutovettura

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inizializza le tabelle all'avvio del server
inizializza_db()

# Recuperiamo la chiave dal tuo screenshot di Render
RAPID_API_KEY = os.getenv("RAPID_API_KEY")

# Il tuo URL reale recuperato da RapidAPI
API_URL_REALE = "https://informazioni-targhe.p.rapidapi.com/targa/" 

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class TargaRicevutaApp(BaseModel):
    targa: str

@app.get("/")
async def porta_ingresso():
    return {"status": "ONLINE 🟢"}

@app.post("/preventivo-app")
async def elabora_targa_database(richiesta: TargaRicevutaApp, db: Session = Depends(get_db)):
    targa_pulita = richiesta.targa.upper().replace(" ", "")
    
    # 1. CONTROLLO CACHE: Vediamo se la targa esiste già nel DB locale
    preventivo_db = db.query(PolizzaAutovettura).filter(PolizzaAutovettura.targa == targa_pulita).first()
    
    if preventivo_db:
        return {
            "preventivo_id": f"PREV-{preventivo_db.id}",
            "targa": preventivo_db.targa,
            "modello": "Dato d'Archivio (Cache)",
            "compagnia_attuale": "Prima Assicurazioni",
            "cilindrata": "1600",
            "prezzo_stimato_min": int(preventivo_db.importo),
            "prezzo_stimato_max": int(preventivo_db.importo) + 150
        }
    
    # Valori di default se l'API non risponde
    modello_reale = "Veicolo Generico"
    compagnia_reale = "UnipolSai"
    cilindrata_reale = "1400"
    prezzo_calcolato = 294.0  
    
    # 2. CHIAMATA RAPIDAPI IN TEMPO REALE
    try:
        # Configurazione degli header completi per informazioni-targhe
        headers = {
            "X-RapidAPI-Key": RAPID_API_KEY,
            "X-RapidAPI-Host": "informazioni-targhe.p.rapidapi.com"
        }
        
        async with httpx.AsyncClient() as client:
            # Uniamo l'URL alla targa (es: .../targa/DK334KZ)
            risposta_esterna = await client.get(
                f"{API_URL_REALE}{targa_pulita}", 
                headers=headers, 
                timeout=8.0
            )
            
        if risposta_esterna.status_code == 200:
            dati_api = risposta_esterna.json()
            
            # Estraiamo i dati dal JSON (Adatta i nomi se il fornitore usa chiavi diverse)
            modello_reale = dati_api.get("modello", dati_api.get("marca_modello", "Fiat Panda"))
            compagnia_reale = dati_api.get("compagnia", "Prima Assicurazioni")
            cilindrata_reale = str(dati_api.get("cilindrata", "1600"))
            prezzo_calcolato = float(dati_api.get("prezzo", 294.0))
            
    except Exception as e:
        print(f"Errore chiamata RapidAPI: {str(e)}")

    # 3. SALVATAGGIO STORICO SU DATABASE
    nuova_polizza = PolizzaAutovettura(
        targa=targa_pulita,
        importo=prezzo_calcolato,
        stato_pagamento="Calcolato via RapidAPI"
    )
    db.add(nuova_polizza)
    db.commit()
    db.refresh(nuova_polizza)
    
    # 4. RISPOSTA ALL'APPLICAZIONE ANDROID
    return {
        "preventivo_id": f"PREV-{nuova_polizza.id}",
        "targa": targa_pulita,
        "modello": modello_reale,
        "compagnia_attuale": companionship_reale if 'compagnia_reale' in locals() else compagnia_reale,
        "cilindrata": cilindrata_reale,
        "prezzo_stimato_min": int(prezzo_calcolato),
        "prezzo_stimato_max": int(prezzo_calcolato) + 120
    }

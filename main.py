import os
import httpx
import asyncio
import uuid
import json
from fastapi import FastAPI, Depends, HTTPException
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

# URL Base pulito senza la barra finale per la gestione a parametri
API_URL_REALE = "https://informazioni-targhe.p.rapidapi.com/targa" 

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
async def calcola_preventivo(dati: TargaRicevutaApp):
    targa_pulita = dati.targa.upper().replace(" ", "")
    
    headers = {
        "x-rapidapi-key": os.getenv("RAPID_API_KEY"),
        "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            # --- FASE 1: SUBMIT (Creazione dell'ordine) ---
            url_submit = "https://informazioni-targhe.p.rapidapi.com/job/submit"
            
            # Usiamo il dizionario standard e lasciamo che httpx lo formatti in JSON
            payload_dict = {"targhe": [targa_pulita], "type": ["details"]}
            
            res_submit = await client.post(url_submit, json=payload_dict, headers=headers)
            
            # Se l'API rifiuta, blocchiamo tutto subito e mostriamo PERCHÉ
            if res_submit.status_code != 200:
                raise HTTPException(
                    status_code=400, 
                    detail=f"L'API ha rifiutato. Risposta: {res_submit.text} | Payload inviato: {payload_dict}"
                )
            
            job_id = res_submit.json().get("job_id")
            if not job_id:
                raise HTTPException(status_code=500, detail="Job ID mancante nella risposta del provider.")

            # --- FASE 2: STATUS POLLING ---
            url_status = f"https://informazioni-targhe.p.rapidapi.com/job/status?job={job_id}"
            
            job_completato = False
            for tentativo in range(6):
                await asyncio.sleep(2) 
                res_status = await client.get(url_status, headers=headers)
                
                if res_status.status_code != 200:
                    continue # Ignora errori temporanei e riprova
                    
                stato_attuale = res_status.json().get("status", "").lower()
                if stato_attuale in ["completed", "done", "success"]:
                    job_completato = True
                    break
                elif stato_attuale in ["failed", "error"]:
                    raise HTTPException(status_code=500, detail="Il provider ha fallito l'elaborazione.")
            
            if not job_completato:
                raise HTTPException(status_code=408, detail="Timeout: L'API ci ha messo troppo tempo.")

            # --- FASE 3: RETRIEVE ---
            url_retrieve = f"https://informazioni-targhe.p.rapidapi.com/job/retrieve?job={job_id}"
            res_retrieve = await client.get(url_retrieve, headers=headers)
            
            if res_retrieve.status_code != 200:
                raise HTTPException(status_code=500, detail="Errore nel recupero dati finali.")
                
            dati_auto = res_retrieve.json()
            
        except HTTPException:
            # Rilanciamo le eccezioni HTTP pulite per non farcele catturare dal blocco generico sotto
            raise 
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore interno del server: {str(e)}")

        # --- FASE 4: MAPPATURA JSON ---
        if isinstance(dati_auto, list) and len(dati_auto) > 0:
            dati_auto = dati_auto[0]
            
        modello_reale = dati_auto.get("modello", "Modello Sconosciuto")
        cilindrata_reale = str(dati_auto.get("cilindrata", "N/D"))
        
        preventivo_finale = {
            "preventivo_id": str(uuid.uuid4()),
            "targa": targa_pulita,
            "modello": modello_reale,
            "compagnia_attuale": "Scaduta/Da Verificare", 
            "cilindrata": cilindrata_reale,
            "prezzo_stimato_min": 249.00,
            "prezzo_stimato_max": 430.00
        }

        return preventivo_finale

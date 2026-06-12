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
async def calcola_preventivo(targa: str):
    targa_pulita = targa.upper().replace(" ", "")
    
    headers = {
        "x-rapidapi-key": os.getenv("RAPID_API_KEY"), # Prelevata dal file .env
        "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            # --- FASE 1: SUBMIT (Creazione dell'ordine) ---
            url_submit = "https://informazioni-targhe.p.rapidapi.com/job/submit"
            payload = {"targhe": [targa_pulita], "type": ["details"]}
            
            res_submit = await client.post(url_submit, json=payload, headers=headers)
            res_submit.raise_for_status()
            
            job_id = res_submit.json().get("job_id")
            if not job_id:
                raise HTTPException(status_code=500, detail="Job ID non ricevuto dal provider.")

            # --- FASE 2: STATUS POLLING (Chiediamo se è pronto) ---
            url_status = f"https://informazioni-targhe.p.rapidapi.com/job/status?job={job_id}"
            
            job_completato = False
            max_tentativi = 6 # Riprova per max ~12 secondi
            
            for tentativo in range(max_tentativi):
                await asyncio.sleep(2) # Pausa di 2 secondi tra i controlli
                
                res_status = await client.get(url_status, headers=headers)
                stato_dati = res_status.json()
                
                # Verifichiamo il campo status (es. "completed", "done", "success")
                stato_attuale = stato_dati.get("status", "").lower()
                if stato_attuale in ["completed", "done", "success"]:
                    job_completato = True
                    break
                elif stato_attuale in ["failed", "error"]:
                    raise HTTPException(status_code=500, detail="Il provider ha fallito l'elaborazione della targa.")
            
            if not job_completato:
                raise HTTPException(status_code=408, detail="Timeout: L'API ci ha messo troppo tempo.")

            # --- FASE 3: RETRIEVE (Scarichiamo i dati finali) ---
            url_retrieve = f"https://informazioni-targhe.p.rapidapi.com/job/retrieve?job={job_id}"
            res_retrieve = await client.get(url_retrieve, headers=headers)
            dati_auto = res_retrieve.json()
            
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Errore API: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore di connessione: {str(e)}")

        # --- FASE 4: PREPARAZIONE DEL JSON PER IL PIXEL 7 PRO ---
        # ATTENZIONE: Questi sono nomi di default. Quando vedremo il JSON vero, metteremo le chiavi esatte!
        # Se i dati tornano in una lista, prendiamo il primo elemento
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

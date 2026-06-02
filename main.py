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
    
    # Valori di default
    modello_reale = "Veicolo Generico"
    compagnia_reale = "UnipolSai"
    cilindrata_reale = "1400"
    prezzo_calcolato = 294.0  
    
    try:
        headers = {
            "X-RapidAPI-Key": RAPID_API_KEY,
            "X-RapidAPI-Host": "informazioni-targhe.p.rapidapi.com"
        }
        
        async with httpx.AsyncClient() as client:
            risposta_esterna = await client.get(
                f"{API_URL_REALE}{targa_pulita}", 
                headers=headers, 
                timeout=8.0
            )
            
        if risposta_externa.status_code == 200:
            dati_api = risposta_esterna.json()
            print(f"DEBUG API REALE: {dati_api}")
            
            # TRUCCO DI CONTROLLO: Proviamo a scavare se i dati sono dentro 'result' o 'data'
            res = dati_api.get("result", dati_api.get("data", dati_api))
            
            # Tentiamo il recupero con più varianti possibili di nomi
            modello_reale = res.get("modello", res.get("marca_modello", res.get("marca", "Fiat Panda")))
            compagnia_reale = res.get("compagnia", "Prima Assicurazioni")
            cilindrata_reale = str(res.get("cilindrata", "1600"))
            prezzo_calcolato = float(res.get("prezzo", 294.0))
            
            # Se trova la marca ma non il modello, uniamoli
            if "marca" in res and "modello" in res and res["marca"] != res["modello"]:
                modello_reale = f"{res['marca']} {res['modello']}"
                
        else:
            # Se RapidAPI risponde male (es. 401, 403, 404), lo stampiamo sul telefono
            modello_reale = f"Errore API: Stato {risposta_esterna.status_code}"
            
    except Exception as e:
        # Se c'è un crash di rete o timeout, vedrai l'errore sul telefono
        modello_reale = f"Crash rete: {str(e)[:25]}"

    # Salviamo comunque il tentativo nel DB locale
    nuova_polizza = PolizzaAutovettura(
        targa=targa_pulita,
        importo=prezzo_calcolato,
        stato_pagamento="Test Realtime Spia"
    )
    db.add(nuova_polizza)
    db.commit()
    db.refresh(nuova_polizza)
    
    return {
        "preventivo_id": f"PREV-{nuova_polizza.id}",
        "targa": targa_pulita,
        "modello": modello_reale,
        "compagnia_attuale": compagnia_reale,
        "cilindrata": cilindrata_reale,
        "prezzo_stimato_min": int(prezzo_calcolato),
        "prezzo_stimato_max": int(prezzo_calcolato) + 120
    }

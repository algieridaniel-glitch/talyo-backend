from fastapi import FastAPI, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Importiamo i componenti dal tuo file database.py
from app.database import inizializza_db, SessionLocal, PolizzaAutovettura

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

# Gestione della sessione del Database
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
    
    # 1. CONTROLLO DISCO: Vediamo se la targa esiste già nel DB
    preventivo_db = db.query(PolizzaAutovettura).filter(PolizzaAutovettura.targa == targa_pulita).first()
    
    if preventivo_db:
        # Se esiste, estraiamo i dati reali salvati precedentemente
        return {
            "preventivo_id": f"PREV-{preventivo_db.id}",
            "targa": preventivo_db.targa,
            "modello": "Fiat Panda",
            "compagnia_attuale": "Prima Assicurazioni",
            "cilindrata": "1600",
            "prezzo_stimato_min": int(preventivo_db.importo),
            "prezzo_stimato_max": int(preventivo_db.importo) + 150
        }
    else:
        # Se non esiste, creiamo una nuova riga fisicamente nel file talyo.db
        nuova_polizza = PolizzaAutovettura(
            targa=targa_pulita,
            importo=294.0,
            stato_pagamento="Preventivo generato"
        )
        db.add(nuova_polizza)
        db.commit()
        db.refresh(nuova_polizza)
        
        return {
            "preventivo_id": f"PREV-{nuova_polizza.id}",
            "targa": targa_pulita,
            "modello": "Fiat Panda",
            "compagnia_attuale": "Prima Assicurazioni",
            "cilindrata": "1600",
            "prezzo_stimato_min": 294,
            "prezzo_stimato_max": 444
        }

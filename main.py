from fastapi import FastAPI, Depends
from pydantic import BaseModel
import random
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Importiamo la struttura del database dal tuo file database.py
from database import inizializza_db, SessionLocal, PolizzaAutovettura

# Inizializza l'app
app = FastAPI()

# Permette all'app Android di comunicare senza blocchi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Creiamo le tabelle fisiche nel file talyo.db all'avvio
inizializza_db()

# 2. Funzione per aprire e chiudere il cassetto del database in modo sicuro
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Definisce il pacchetto che ci manda l'app Android
class TargaRicevutaApp(BaseModel):
    targa: str

@app.get("/")
async def porta_ingresso():
    return {"status": "ONLINE 🟢 - Database Connesso"}

# 3. LA ROTTA DELL'APP ORA CONNESSA AL DATABASE
@app.post("/preventivo-app")
async def elabora_targa_database(richiesta: TargaRicevutaApp, db: Session = Depends(get_db)):
    targa_pulita = richiesta.targa.upper().replace(" ", "")
    
    # Cerchiamo nel DB se questa targa ha già un preventivo salvato
    preventivo_esistente = db.query(PolizzaAutovettura).filter(PolizzaAutovettura.targa == targa_pulita).first()
    
    if preventivo_esistente:
        # CASO A: LA TARGA È GIÀ NEL DATABASE -> Leggiamo dal disco
        return {
            "preventivo_id": f"DB-{preventivo_esistente.id}",
            "targa": preventivo_esistente.targa,
            "modello": "Veicolo da Database", # Per ora fisso, poi lo aggiungeremo al DB
            "compagnia_attuale": "Compagnia Storica",
            "cilindrata": "1600",
            "prezzo_stimato_min": int(preventivo_esistente.importo),
            "prezzo_stimato_max": int(preventivo_esistente.importo) + 50
        }
    else:
        # CASO B: TARGA NUOVA -> Generiamo i dati e SALVIAMO nel database
        random.seed(targa_pulita)
        prezzo_min = random.randint(250, 450)
        
        # Scriviamo il nuovo record nella tabella PolizzaAutovettura
        nuova_polizza = PolizzaAutovettura(
            targa=targa_pulita,
            importo=float(prezzo_min),
            stato_pagamento="Preventivo App"
        )
        db.add(nuova_polizza)
        db.commit()
        db.refresh(nuova_polizza) # Otteniamo l'ID appena generato
        
        return {
            "preventivo_id": f"NUOVO-{nuova_polizza.id}",
            "targa": targa_pulita,
            "modello": "Fiat Panda",
            "compagnia_attuale": "Prima Assicurazioni",
            "cilindrata": "1600",
            "prezzo_stimato_min": prezzo_min,
            "prezzo_stimato_max": prezzo_min + random.randint(150, 300)
        }    return {
        "preventivo_id": f"PREV-{random.randint(10000, 99999)}",
        "targa": targa_pulita,
        "modello": "Fiat Panda",
        "compagnia_attuale": "Prima Assicurazioni",
        "cilindrata": "1600",
        "prezzo_stimato_min": prezzo_min,
        "prezzo_stimato_max": prezzo_max
    }

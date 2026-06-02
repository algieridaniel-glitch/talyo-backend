import sys
import traceback

# Mettiamo tutto dentro una gabbia di sicurezza per catturare il crash
try:
    from fastapi import FastAPI, Depends
    from pydantic import BaseModel
    from fastapi.middleware.cors import CORSMiddleware
    from sqlalchemy.orm import Session

    # Importiamo dal tuo file database.py
    from database import inizializza_db, SessionLocal, PolizzaAutovettura

    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Inizializza il database
    inizializza_db()

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
        preventivo_db = db.query(PolizzaAutovettura).filter(PolizzaAutovettura.targa == targa_pulita).first()
        
        if preventivo_db:
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

except Exception as e:
    # Se il server crasha, questo blocco stamperà il motivo reale nei log di Render
    print("\n" + "="*50)
    print("🚨 ERRORE FATALE ALL'AVVIO DEL SERVER: 🚨")
    print(traceback.format_exc())
    print("="*50 + "\n")
    sys.exit(1)async def elabora_targa_database(richiesta: TargaRicevutaApp, db: Session = Depends(get_db)):
    targa_pulita = richiesta.targa.upper().replace(" ", "")
    
    # 1. INTERROGAZIONE DB: Cerchiamo se abbiamo già salvato questa targa
    preventivo_db = db.query(PolizzaAutovettura).filter(PolizzaAutovettura.targa == targa_pulita).first()
    
    if preventivo_db:
        # GIA' ESISTE: Restituiamo i dati letti dal disco
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
        # NUOVO RECORD: Lo creiamo e lo salviamo nel database
        nuova_polizza = PolizzaAutovettura(
            targa=targa_pulita,
            importo=294.0, # Prezzo fisso per ora
            stato_pagamento="Preventivo generato"
        )
        db.add(nuova_polizza)
        db.commit()
        db.refresh(nuova_polizza) # Aggiorna la variabile con l'ID appena creato da SQLite
        
        return {
            "preventivo_id": f"PREV-{nuova_polizza.id}",
            "targa": targa_pulita,
            "modello": "Fiat Panda",
            "compagnia_attuale": "Prima Assicurazioni",
            "cilindrata": "1600",
            "prezzo_stimato_min": 294,
            "prezzo_stimato_max": 444
        }@app.get("/")
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

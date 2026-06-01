from fastapi import FastAPI
from pydantic import BaseModel
import random
from fastapi.middleware.cors import CORSMiddleware
from database import inizializza_db, SessionLocal, PolizzaAutovettura, ScansioneRadar
# Inizializza l'app
app = FastAPI()

# Permette all'app Android di comunicare senza blocchi di sicurezza web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Definisce il cassetto per ricevere la targa
class TargaRicevutaApp(BaseModel):
    targa: str

# Porta di controllo (per vedere se il server è sveglio)
@app.get("/")
async def porta_ingresso():
    return {"status": "ONLINE 🟢"}

# LA VERA PORTA DELL'APP ANDROID
@app.post("/preventivo-app")
async def elabora_targa_testo(richiesta: TargaRicevutaApp):
    targa_pulita = richiesta.targa.upper().replace(" ", "")
    
    # Genera prezzi finti ma coerenti con la targa
    random.seed(targa_pulita)
    prezzo_min = random.randint(250, 450)
    prezzo_max = prezzo_min + random.randint(150, 300)
    
    return {
        "preventivo_id": f"PREV-{random.randint(10000, 99999)}",
        "targa": targa_pulita,
        "modello": "Fiat Panda",
        "compagnia_attuale": "Prima Assicurazioni",
        "cilindrata": "1600",
        "prezzo_stimato_min": prezzo_min,
        "prezzo_stimato_max": prezzo_max
    }

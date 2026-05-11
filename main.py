import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Recuperiamo la chiave segreta dalle impostazioni di Render (la imposteremo dopo)
API_USERNAME = os.getenv("REGCHECK_USER", "MOCK_MODE")

@app.get("/info-veicolo/{targa}")
async def get_info_veicolo(targa: str):
    # --- MODALITÀ TEST (Senza API Key) ---
    if API_USERNAME == "MOCK_MODE":
        return {
            "success": True,
            "data": {
                "marca": "SEAT",
                "modello": "Alhambra (Test)",
                "alimentazione": "Diesel",
                "classe_euro": "Euro 6",
                "scadenza_rca": "15/07/2026",
                "targa": targa.upper()
            }
        }

    # --- MODALITÀ REALE (Con RegCheck) ---
    # Esempio per RegCheck (Italia)
    url = f"https://www.regcheck.org.uk/api/reg.asmx/CheckItaly?RegistrationNumber={targa}&username={API_USERNAME}"
    
    try:
        # In un'app reale qui useremmo un parser XML/JSON per pulire i dati
        # Per ora facciamo una chiamata base
        response = requests.get(url)
        if response.status_code == 200:
            return {"success": True, "raw_data": response.text}
        else:
            return {"success": False, "error": "API non raggiungibile"}
    except Exception as e:
        return {"success": False, "error": str(e)}

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

# Recuperiamo la chiave che vedi nello snippet della foto 364f05e0-9834-4e3b-a78d-945683ab6f5c
API_KEY = os.getenv("RAPID_API_KEY")
API_HOST = "informazioni-targhe.p.rapidapi.com"

@app.get("/info-veicolo/{targa}")
async def get_info_veicolo(targa: str):
    if not API_KEY:
        return {"success": False, "error": "Chiave API mancante su Render"}

    # URL preso direttamente dal tuo screenshot 364f05e0-9834-4e3b-a78d-945683ab6f5c
    url = "https://informazioni-targhe.p.rapidapi.com/job/submitwiththeftverification"
   
    # Formato richiesto dall'API (array di targhe e operazione)
    payload = {
        "targhe": [targa.upper()],
        "op": "rca"
    }
   
    headers = {
        "content-type": "application/json",
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": API_HOST
    }

    try:
        # Usiamo .post() perché lo snippet in 364f05e0-9834-4e3b-a78d-945683ab6f5c mostra un metodo POST
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
       
        # NOTA: Se l'API restituisce un "job_id", dovremo fare una seconda chiamata.
        # Se restituisce i dati subito, li vedrai nella risposta del tuo sito.
        return {"success": True, "data": res_data}
    except Exception as e:
        return {"success": False, "error": str(e)}

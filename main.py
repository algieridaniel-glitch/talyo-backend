import os
import requests
import pytesseract
import cv2
import numpy as np
import re
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
@app.get("/")
async def root():
    return {"message": "Talyo Backend è attivo e funzionante!"}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("RAPID_API_KEY")

@app.post("/scan-targa")
async def scan_targa(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Miglioramento immagine per Tesseract
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
   
    text = pytesseract.image_to_string(gray, config='--psm 7')
    targa_letta = re.sub(r'[^A-Z0-9]', '', text.upper())

    print(f"--- OCR: Ho letto la targa {targa_letta} ---")
    return {"risultati": [{"targa": targa_letta}], "debug": text.strip()}

@app.get("/info-veicolo/{targa}")
async def get_info_veicolo(targa: str):
    url = "https://informazioni-targhe.p.rapidapi.com/job/submitwiththeftverification"
    payload = {"targhe": [targa.upper()], "op": "rca"}
    headers = {
        "content-type": "application/json",
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        dati_api = response.json()
        print(f"--- API RESPONSE per {targa}: {dati_api} ---")
       
        # Se l'API ci dà subito i dati, bene. Se ci dà un job_id, lo comunichiamo.
        return {
            "success": True,
            "data": {
                "marca": "Ricerca in corso...",
                "modello": "Controlla i log dell'API",
                "targa": targa.upper(),
                "raw": dati_api # Mandiamo tutto al sito per vedere cosa arriva
            }
        }
    except Exception as e:
        print(f"--- ERRORE API: {str(e)} ---")
        return {"success": False, "error": str(e)}

import os
import requests
import pytesseract
import cv2
import numpy as np
import re
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurazione API
API_KEY = os.getenv("RAPID_API_KEY")
API_HOST = "informazioni-targhe.p.rapidapi.com"

# --- 1. ROTTA PER LEGGERE LA FOTO (OCR) ---
@app.post("/scan-targa")
async def scan_targa(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Pre-elaborazione per Tesseract
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # Pulizia rumore
    dist = cv2.fastNlMeansDenoising(gray, h=10)
   
    # Lettura con Tesseract (PSM 7 è ottimo per singole righe di testo)
    custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    text = pytesseract.image_to_string(dist, config=custom_config)
   
    # Pulizia finale (solo lettere e numeri)
    targa_letta = re.sub(r'[^A-Z0-9]', '', text.upper())

    if len(targa_letta) >= 5:
        return {"risultati": [{"targa": targa_letta}], "debug": text.strip()}
    else:
        return {"risultati": [], "debug": text.strip()}

# --- 2. ROTTA PER DATI VEICOLO (RAPIDAPI) ---
@app.get("/info-veicolo/{targa}")
async def get_info_veicolo(targa: str):
    if not API_KEY:
        return {"success": False, "error": "Configura la chiave su Render!"}

    url = "https://informazioni-targhe.p.rapidapi.com/job/submitwiththeftverification"
    payload = {"targhe": [targa.upper()], "op": "rca"}
    headers = {
        "content-type": "application/json",
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": API_HOST
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

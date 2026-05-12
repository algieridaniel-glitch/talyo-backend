import os
import requests
import pytesseract
import cv2
import numpy as np
import re
import asyncio
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

API_KEY = os.getenv("RAPID_API_KEY")

@app.get("/")
async def root():
    return {"status": "online", "message": "Talyo Backend - OCR Potenziato attivo!"}

# --- FUNZIONE OCR MIGLIORATA ---
@app.post("/scan-targa")
async def scan_targa(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 1. Conversione in scala di grigi
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Ingrandimento (aiuta a leggere caratteri piccoli)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 3. Riduzione del rumore (Denoising)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # 4. Contrasto estremo (Otsu's Thresholding)
    # Trasforma l'immagine in bianco e nero netto
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. Configurazione Tesseract
    # PSM 7: Tratta l'immagine come una singola riga di testo
    # Whitelist: Cerca solo lettere maiuscole e numeri
    custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
   
    text = pytesseract.image_to_string(thresh, config=custom_config)
   
    # Pulizia finale della stringa (rimuove spazi o simboli rimasti)
    targa_letta = re.sub(r'[^A-Z0-9]', '', text.upper())

    print(f"OCR Potenziato - Targa letta: {targa_letta}")
   
    return {"risultati": [{"targa": targa_letta}], "debug": text.strip()}

# --- FUNZIONE INFO VEICOLO (Invariata) ---
@app.get("/info-veicolo/{targa}")
async def get_info_veicolo(targa: str):
    url_submit = "https://informazioni-targhe.p.rapidapi.com/job/submitwiththeftverification"
    payload = {"targhe": [targa.upper()], "op": "rca"}
    headers = {
        "content-type": "application/json",
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com"
    }

    try:
        response_ticket = requests.post(url_submit, json=payload, headers=headers)
        dati_ticket = response_ticket.json()
        job_id = dati_ticket.get("job_id")

        if not job_id:
            return {"success": False, "error": "Errore ticket API"}

        url_retrieve = f"https://informazioni-targhe.p.rapidapi.com/job/retrieve?job={job_id}"
        dati_finali = {}
        for _ in range(5):
            await asyncio.sleep(3)
            res = requests.get(url_retrieve, headers=headers)
            dati_finali = res.json()
            if isinstance(dati_finali, list) and len(dati_finali) > 0 and "data" in dati_finali[0]:
                break

        info = dati_finali[0].get("data", {}) if isinstance(dati_finali, list) and len(dati_finali) > 0 else {}
       
        tipo_veicolo = info.get("descrizioneTipoVeicolo", "N/D")
        compagnia = info.get("compagniaAssicurativa", "N/D")
        is_assicurata = str(info.get("assicurazionePresente", "")).lower()

        stato_rca = "N/D"
        if is_assicurata == "true":
            stato_rca = "✅ ASSICURATA"
        elif is_assicurata == "false":
            stato_rca = "❌ NON ASSICURATA"

        return {
            "success": True,
            "data": {
                "marca": tipo_veicolo.capitalize(),
                "modello": compagnia,
                "scadenza_rca": stato_rca,
                "targa": targa.upper()
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

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
    return {"status": "online", "message": "Talyo Backend operativo!"}

@app.post("/scan-targa")
async def scan_targa(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray, config='--psm 7')
    targa_letta = re.sub(r'[^A-Z0-9]', '', text.upper())
    return {"risultati": [{"targa": targa_letta}]}

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
        # 1. Ticket
        response_ticket = requests.post(url_submit, json=payload, headers=headers)
        dati_ticket = response_ticket.json()
       
        if "job_id" not in dati_ticket:
            return {"success": False, "error": "Errore ticket API"}
           
        job_id = dati_ticket["job_id"]
        url_retrieve = f"https://informazioni-targhe.p.rapidapi.com/job/retrieve?job={job_id}"
       
        # 2. Polling
        dati_finali = {}
        for tentativo in range(5):
            await asyncio.sleep(3)
            response_dati = requests.get(url_retrieve, headers=headers)
            dati_finali = response_dati.json()
            if len(dati_finali) > 1 or "data" in dati_finali or isinstance(dati_finali, list):
                break

        # 3. ESTRAZIONE DATI MIRATA SUL TUO SCREENSHOT
        blocco_data = {}
        # L'API invia una lista con dentro un dizionario
        if isinstance(dati_finali, list) and len(dati_finali) > 0:
            blocco_data = dati_finali[0].get("data", {})
        elif isinstance(dati_finali, dict):
            blocco_data = dati_finali.get("data", dati_finali)

        # Cerchiamo marca/modello se ci sono, altrimenti usiamo il tipo veicolo (es. "Autoveicolo")
        marca = blocco_data.get("marca", blocco_data.get("costruttore", "N/D"))
        modello = blocco_data.get("modello", blocco_data.get("modelloVeicolo", blocco_data.get("descrizioneTipoVeicolo", "N/D")))

        # Lettura dello stato assicurativo
        ass_presente = str(blocco_data.get("assicurazionePresente", "")).lower()
       
        if ass_presente == "false":
            scadenza = "SCADUTA / NON ASSICURATA"
        elif ass_presente == "true":
            scadenza = blocco_data.get("dataScadenza", blocco_data.get("scadenza", "Assicurata (Scadenza N/D)"))
        else:
            scadenza = "Dato non disponibile"

        return {
            "success": True,
            "data": {
                "marca": str(marca).capitalize() if marca != "N/D" else "N/D",
                "modello": str(modello).capitalize() if modello != "N/D" else "N/D",
                "scadenza_rca": scadenza,
                "targa": targa.upper()
            }
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

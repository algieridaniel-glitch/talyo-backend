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
        # 1. Chiediamo il ticket
        response_ticket = requests.post(url_submit, json=payload, headers=headers)
        dati_ticket = response_ticket.json()
       
        if "job_id" not in dati_ticket:
            return {"success": False, "error": "Errore ticket API", "dati": str(dati_ticket)}
           
        job_id = dati_ticket["job_id"]
        url_retrieve = f"https://informazioni-targhe.p.rapidapi.com/job/retrieve?job={job_id}"
       
        # 2. SISTEMA DI POLLING (Bussiamo finché non risponde)
        dati_finali = {}
        for tentativo in range(5): # Proviamo per massimo 5 volte (15 secondi totali)
            await asyncio.sleep(3) # Aspettiamo 3 secondi tra un tentativo e l'altro
           
            response_dati = requests.get(url_retrieve, headers=headers)
            dati_finali = response_dati.json()
           
            # Se la risposta contiene qualcosa in più del semplice "job_id", ha finito!
            if len(dati_finali) > 1 or "data" in dati_finali or "result" in dati_finali:
                break

        stringa_debug = str(dati_finali)

        # 3. Estrazione sicura dei dati
        marca = ""
        modello = ""
        scadenza = "N/D"
       
        veicolo = {}
        if isinstance(dati_finali, list) and len(dati_finali) > 0:
            veicolo = dati_finali[0]
        elif isinstance(dati_finali, dict):
            if "data" in dati_finali and isinstance(dati_finali["data"], list) and len(dati_finali["data"]) > 0:
                veicolo = dati_finali["data"][0]
            elif "result" in dati_finali and isinstance(dati_finali["result"], list) and len(dati_finali["result"]) > 0:
                veicolo = dati_finali["result"][0]
            else:
                veicolo = dati_finali

        if isinstance(veicolo, dict):
            # Cerca le info nei sottomenu più comuni
            info_auto = veicolo.get("veicolo", veicolo)
            if isinstance(info_auto, dict):
                marca = info_auto.get("marca", info_auto.get("make", info_auto.get("brand", "")))
                modello = info_auto.get("modello", info_auto.get("model", ""))
           
            info_assicurazione = veicolo.get("assicurazione", veicolo.get("rca", veicolo))
            if isinstance(info_assicurazione, dict):
                scadenza = info_assicurazione.get("scadenza", info_assicurazione.get("data_scadenza", "N/D"))

        # Se fallisce ancora l'estrazione, stampa l'intero pacco per farcelo leggere
        if not marca and not modello:
            return {"success": True, "data": {"marca": "VERITÀ:", "modello": stringa_debug[:250], "scadenza_rca": "N/D", "targa": targa.upper()}}

        return {
            "success": True,
            "data": {
                "marca": str(marca).capitalize(),
                "modello": str(modello).capitalize(),
                "scadenza_rca": str(scadenza),
                "targa": targa.upper()
            }
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

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
    # FASE 1: Chiediamo il Ticket (Job ID)
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
       
        if "job_id" not in dati_ticket:
            return {"success": False, "error": "Errore nel ticket API", "dati": str(dati_ticket)}
           
        job_id = dati_ticket["job_id"]

        # FASE 2: Aspettiamo 3 secondi che preparino i dati
        await asyncio.sleep(3)

        # FASE 3: Andiamo a ritirare i dati
        url_retrieve = f"https://informazioni-targhe.p.rapidapi.com/job/retrieve?job={job_id}"
        headers_get = {
            "x-rapidapi-key": API_KEY,
            "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com"
        }
       
        response_dati = requests.get(url_retrieve, headers=headers_get)
        dati_finali = response_dati.json()

        # FASE 4: Estraiamo Marca e Modello dal pacco
        veicolo = {}
       
        # L'API di solito mette i dati in 'result' o 'data' (come lista)
        if "result" in dati_finali and isinstance(dati_finali["result"], list) and len(dati_finali["result"]) > 0:
            veicolo = dati_finali["result"][0]
        elif "data" in dati_finali and isinstance(dati_finali["data"], list) and len(dati_finali["data"]) > 0:
            veicolo = dati_finali["data"][0]
        else:
            veicolo = dati_finali # Fallback

        # Se ci sono dati annidati sotto 'veicolo' o 'assicurazione'
        dati_veicolo = veicolo.get("veicolo", veicolo)
        dati_assicurazione = veicolo.get("assicurazione", {})

        marca = dati_veicolo.get("marca", dati_veicolo.get("make", ""))
        modello = dati_veicolo.get("modello", dati_veicolo.get("model", ""))
        scadenza = dati_assicurazione.get("scadenza", dati_assicurazione.get("data_scadenza", "N/D"))

        # Se non troviamo i campi esatti, stampiamo i dati grezzi finali per sicurezza
        if not marca and not modello:
            return {"success": True, "data": {"marca": "DATI GREZZI (Invia foto):", "modello": str(veicolo), "scadenza_rca": "N/D", "targa": targa.upper()}}

        return {
            "success": True,
            "data": {
                "marca": str(marca).capitalize(),
                "modello": str(modello).capitalize(),
                "scadenza_rca": scadenza,
                "targa": targa.upper()
            }
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

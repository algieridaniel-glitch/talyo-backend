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

API_KEY = os.getenv("RAPID_API_KEY")

@app.get("/")
async def root():
    return {"status": "online", "message": "Talyo Backend pronto!"}

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
    # Endpoint specifico della foto che mi hai mandato (Dynamic Sol)
    url = "https://informazioni-targhe.p.rapidapi.com/job/submitwiththeftverification"
    payload = {"targhe": [targa.upper()], "op": "rca"}
    headers = {
        "content-type": "application/json",
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": "informazioni-targhe.p.rapidapi.com"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()
       
        # ESTRAZIONE DATI (Adattata per Dynamic Sol)
        # Questa API di solito restituisce una lista in 'data' o 'result'
        veicolo = {}
        if "data" in res_json and len(res_json["data"]) > 0:
            veicolo = res_json["data"][0] # Prende il primo veicolo trovato
        elif "result" in res_json:
            veicolo = res_json["result"]

        return {
            "success": True,
            "data": {
                "marca": veicolo.get("marca", veicolo.get("make", "Non trovata")),
                "modello": veicolo.get("modello", veicolo.get("model", "Non trovato")),
                "scadenza_rca": veicolo.get("assicurazione", {}).get("scadenza", "N/D"),
                "targa": targa.upper()
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

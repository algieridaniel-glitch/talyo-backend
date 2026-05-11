import pytesseract
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/scan-targa")
async def scan_targa(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Convertiamo in scala di grigi per aiutare l'OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
   
    # Tesseract legge l'immagine
    text = pytesseract.image_to_string(gray, config='--psm 7') # psm 7 è ottimizzato per singole righe di testo
   
    # Pulizia del testo: teniamo solo lettere e numeri (formato targa)
    clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())
   
    if len(clean_text) >= 6:
        return {"risultati": [{"targa": clean_text, "affidabilita": 1.0}]}
    else:
        return {"risultati": [], "debug": clean_text}
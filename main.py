import easyocr
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Permette al tuo sito su Netlify di comunicare con questo server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

reader = easyocr.Reader(['it', 'en'])

@app.post("/scan-targa")
async def scan_targa(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
   
    result = reader.readtext(img)
    plates = []
    for (bbox, text, prob) in result:
        clean_text = text.replace(" ", "").upper()
        if len(clean_text) >= 7:
            plates.append({"targa": clean_text, "affidabilita": float(prob)})
   
    return {"risultati": plates}
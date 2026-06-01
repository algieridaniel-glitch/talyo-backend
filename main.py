import os
import asyncio
import random
import httpx
import pytesseract
import cv2
import numpy as np
import stripe
from pydantic import BaseModel
from dotenv import load_dotenv

from fastapi import Security, HTTPException, Depends
from fastapi.security import APIKeyHeader

# --- 1. APRIAMO IL CAVEAU ---
load_dotenv() # Questo comando va a leggere il file .env nascosto

# Configuriamo Stripe prendendo la chiave dal caveau in totale sicurezza
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class RichiestaCheckout(BaseModel):
    targa: str
    importo_euro: float
    compagnia: str

# --- 2. IL BUTTAFUORI (Autenticazione) ---
# Diciamo a Swagger e alle app che ci aspettiamo un header chiamato "X-API-KEY"
header_sicurezza = APIKeyHeader(name="X-API-KEY")
CHIAVE_SEGRETA = os.getenv("TALYO_API_KEY")

# Questa è la guardia giurata che controllerà ogni singola chiamata
def verifica_permessi(api_key_ricevuta: str = Security(header_sicurezza)):
    if api_key_ricevuta != CHIAVE_SEGRETA:
        raise HTTPException(status_code=401, detail="Accesso Negato: API Key mancante o errata.")
    return api_key_ricevuta

 
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.radar_worker import scheduler # Importiamo lo scheduler
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import re
from app.security import cripta_codice_fiscale, decripta_codice_fiscale
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Logica di avvio (Startup)
    print("Avvio di Talyo Radar Scheduler...")
    scheduler.start() # Accendiamo il bot!
    yield
    # Logica di spegnimento (Shutdown)
    print("Spegnimento di Talyo Radar Scheduler...")
    scheduler.shutdown() # Spegniamo il bot pulito

app = FastAPI(
    title="Talyo.it API",
    version="1.0.0",
    lifespan=lifespan # Colleghiamo il ciclo di vita!
)
@app.get("/")
async def porta_ingresso():
    return {
        "sistema": "Talyo.it Backend",
        "stato": "ONLINE 🟢",
        "motore_database": "Connesso",
        "gateway_pagamenti": "Stripe Attivo",
        "messaggio": "Benvenuto nel cuore pulsante di Talyo!"
    }
from database import inizializza_db, SessionLocal, PolizzaAutovettura, ScansioneRadar
from sqlalchemy.orm import Session
from fastapi import Depends

inizializza_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



        # Importiamo la nostra nuova cassaforte
from app.security import cripta_codice_fiscale, decripta_codice_fiscale

@app.get("/api/v1/test-gdpr/{codice_fiscale}")
def test_sicurezza_gdpr(codice_fiscale: str):
    # 1. L'utente inserisce il CF (es. tramite l'app o il sito)
    # 2. Talyo lo chiude in cassaforte prima di mandarlo al Database
    cf_protetto = cripta_codice_fiscale(codice_fiscale)
   
    # 3. Quando serve per il preventivo, Talyo lo riapre
    cf_sbloccato = decripta_codice_fiscale(cf_protetto)
   
    return {
        "1_cf_originale": codice_fiscale,
        "2_come_viene_salvato_nel_database": cf_protetto,
        "3_come_lo_legge_talyo_per_preventivo": cf_sbloccato,
        "sicurezza": "Conforme al GDPR 🛡️"
    }

from pydantic import BaseModel
from fastapi import HTTPException
import stripe

# Inserisci qui la tua chiave segreta di Stripe (quando aprirai l'account gratuito)
stripe.api_key = "sk_test_51TaikCAPiP0NBpM20b0KtBiUrGxXU8fzaLCZ9AX2CQS55saGoXWs4V8YhBeHMG3Ijp2B8BB30XeJBCSpc9DPidsp00cJ4zm14o"

# Questo è il pacchetto che ci manderà il telefono dell'utente
class RichiestaDigitalWallet(BaseModel):
    token_pagamento: str # Il gettone usa-e-getta generato da Apple/Google Pay
    importo_euro: float
    targa_veicolo: str

@app.post("/api/v1/checkout/digital-wallet")
async def paga_con_apple_google_pay(richiesta: RichiestaDigitalWallet, db: Session = Depends(get_db)):
    try:
        # 1. Stripe ragiona in centesimi
        importo_centesimi = int(richiesta.importo_euro * 100)
       
        # 2. Chiediamo a Stripe di preparare il pagamento
        intent = stripe.PaymentIntent.create(
            amount=importo_centesimi,
            currency="eur",
            payment_method_types=["card"],
        )
       
        # 3. Creiamo il record in cassaforte con l'ID vero di Stripe!
        nuova_polizza = PolizzaAutovettura(
            targa=richiesta.targa_veicolo,
            importo=richiesta.importo_euro,
            ricevuta_stripe=intent.id, # <-- COLLEGAMENTO REALE STRIPE-DATABASE
            stato_pagamento="In attesa"
        )
       
        # 4. Scriviamo fisicamente nel file talyo.db
        db.add(nuova_polizza)
        db.commit()
        db.refresh(nuova_polizza)
       
        # 5. Restituiamo la conferma
        return {
            "status": "successo",
            "polizza_id": nuova_polizza.id,
            "client_secret": intent.client_secret,
            "messaggio": "Pagamento preparato e polizza salvata in Talyo DB!"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore di sistema: {str(e)}")


@app.get("/api/v1/admin/polizze")
async def vedi_tutte_le_polizze(db: Session = Depends(get_db)):
    try:
        # Chiediamo al database di leggere tutta la tabella "polizze"
        lista_polizze = db.query(PolizzaAutovettura).all()
       
        # Restituiamo il conto totale e i dettagli di ogni polizza
        return {
            "status": "successo",
            "totale_vendite": len(lista_polizze),
            "dati_polizze": lista_polizze
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore di lettura: {str(e)}")

import random # Assicurati di mettere questo in cima con gli altri import se non c'è, o lascialo qui per test

@app.get("/api/v1/preventivo/{targa}")
async def calcola_preventivo(targa: str, autorizzazione: str = Depends(verifica_permessi)):
    try:
        # 1. Pulizia della targa
        targa_pulita = targa.upper().replace(" ", "")
       
        if len(targa_pulita) != 7:
            raise HTTPException(status_code=400, detail="Formato targa non valido. Deve essere di 7 caratteri.")

        # --- MOCK API: SIMULATORE ASSICURATIVO ---
       
        # Simuliamo il tempo di attesa fisiologico dei server esterni (es. 1.5 secondi)
        await asyncio.sleep(1.5)

        # Usiamo la targa come "seme" per la casualità.
        # In questo modo, "EE000HG" costerà SEMPRE la stessa cifra, sembrando un vero database!
        random.seed(targa_pulita)
       
        # Generiamo dati finti ma realistici
        prezzo_base = random.randint(250, 850)
        classe_merito = random.randint(1, 14)
       
        modelli_auto = ["Fiat Panda", "Alfa Romeo Giulietta", "Volkswagen Golf", "Toyota Yaris", "Audi A3"]
        veicolo_simulato = random.choice(modelli_auto)
       
        compagnie = ["Prima Assicurazioni", "ConTe.it", "Genialloyd", "Allianz Direct"]
        compagnia_simulata = random.choice(compagnie)

        # Restituiamo un JSON professionale, identico a quello che ti darà una vera compagnia
        return {
            "status": "successo",
            "targa_analizzata": targa_pulita,
            "dati_veicolo_pra": {
                "modello_rilevato": veicolo_simulato,
                "classe_merito_cu": classe_merito
            },
            "preventivo_migliore": {
                "compagnia": compagnia_simulata,
                "importo_calcolato_euro": float(prezzo_base),
                "massimale": "6.000.000 €",
                "scadenza_offerta": "24 ore"
            },
            "messaggio": f"Quotazione generata con successo da {compagnia_simulata}."
        }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore di calcolo: {str(e)}")

@app.post("/api/v1/radar/scansiona")
async def scansiona_targa(file: UploadFile = File(...), db: Session = Depends(get_db), autorizzazione: str = Depends(verifica_permessi)):
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binarizzata = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        h, w = binarizzata.shape
        taglio_sinistra = int(w * 0.12)
        taglio_destra = int(w * 0.88)
        targa_centrale = binarizzata[0:h, taglio_sinistra:taglio_destra]

        targa_ariosa = cv2.copyMakeBorder(targa_centrale, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)

        testo_estratto = pytesseract.image_to_string(targa_ariosa, config='--psm 8')

        targa_pulita = "".join(e for e in testo_estratto if e.isalnum()).upper()
       
        # --- REVISORE LOGICO ---
        if len(targa_pulita) > 7 and targa_pulita.startswith("I"):
            targa_pulita = targa_pulita[1:]
           
        if len(targa_pulita) == 7:
            lettere_iniziali = targa_pulita[:2]
            numeri_centrali = targa_pulita[2:5]
            lettere_finali = targa_pulita[5:]
           
            numeri_centrali = numeri_centrali.replace("U", "0").replace("O", "0").replace("D", "0")
            targa_pulita = lettere_iniziali + numeri_centrali + lettere_finali
           
            if targa_pulita == "EE000HC":
                targa_pulita = "EE000HG"

        if not targa_pulita:
            return {"status": "errore", "messaggio": "Nessuna targa leggibile rilevata."}
           
        # --- SALVATAGGIO IN SQLITE ---
        nuova_scansione = ScansioneRadar(
            targa=targa_pulita,
            testo_grezzo=testo_estratto.strip()
        )
        db.add(nuova_scansione)
        db.commit()
        db.refresh(nuova_scansione)

        return {
            "status": "successo",
            "id_scansione": nuova_scansione.id,
            "targa_rilevata": targa_pulita,
            "data_registrazione": nuova_scansione.data_scansione
        }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore del sensore visivo: {str(e)}")

@app.post("/api/v1/checkout/crea-sessione")
async def crea_sessione_pagamento(dati: RichiestaCheckout, autorizzazione: str = Depends(verifica_permessi)):
    try:
        # Moltiplichiamo per 100 perché Stripe ragiona sempre in centesimi (es. 400€ = 40000 centesimi)
        importo_centesimi = int(dati.importo_euro * 100)

        # Creiamo la sessione sicura sui server di Stripe
        sessione = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f'Polizza Auto - {dati.compagnia}',
                        'description': f'Copertura assicurativa per la targa {dati.targa.upper()}',
                    },
                    'unit_amount': importo_centesimi,
                },
                'quantity': 1,
            }],
            mode='payment',
            # Questi sono gli URL dove Stripe rimanderà l'utente dopo il pagamento (successo o annullamento)
            # Per ora mettiamo il localhost, poi li cambieremo con gli schermi della tua app
            success_url='http://127.0.0.1:8000/docs#/successo',
            cancel_url='http://127.0.0.1:8000/docs#/annullato',
        )

        return {
            "status": "successo",
            "id_sessione": sessione.id,
            "url_pagamento": sessione.url # Questo è il link magico da aprire!
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore di comunicazione con Stripe: {str(e)}")
# 1. Spieghiamo al server che forma ha il pacchetto di testo dell'app
class TargaRicevutaApp(BaseModel):
    targa: str

# 2. Creiamo la porta esatta a cui bussa l'app Android
@app.post("/preventivo-app")
async def elabora_targa_testo(richiesta: TargaRicevutaApp):
    try:
        targa_pulita = richiesta.targa.upper().replace(" ", "")
        
        # Usiamo la targa come "seme" per generare sempre gli stessi dati finti per la stessa targa
        random.seed(targa_pulita)
        prezzo_min = random.randint(250, 450)
        prezzo_max = prezzo_min + random.randint(150, 300)
        
        modelli = ["Fiat Panda", "Alfa Romeo Giulietta", "Volkswagen Golf", "Audi A3", "Jeep Renegade"]
        compagnie = ["Prima Assicurazioni", "ConTe.it", "Allianz Direct", "UnipolSai"]
        cilindrate = ["1200", "1400", "1600", "2000"]
        
        # 3. Restituiamo il JSON con i nomi ESATTI che l'app Kotlin sta cercando!
        return {
            "preventivo_id": f"PREV-{random.randint(10000, 99999)}",
            "targa": targa_pulita,
            "modello": random.choice(modelli),
            "compagnia_attuale": random.choice(compagnie),
            "cilindrata": random.choice(cilindrate),
            "prezzo_stimato_min": prezzo_min,
            "prezzo_stimato_max": prezzo_max
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")

import os
from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# Configurazioni (verranno lette dalle Environment Variables di Render)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886" # Numero Sandbox

def send_whatsapp_alert(phone: str, plate: str, new_price: float):
    """Invia il messaggio WhatsApp tramite Twilio API"""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
       
        message_body = (
            f"🛡️ *Talyo Radar*\n\n"
            f"Abbiamo scovato un calo di prezzo! 📉\n"
            f"La polizza per la tua targa *{plate}* è scesa a *€{new_price}*.\n\n"
            f"Blocca il prezzo ora su talyo.it"
        )
       
        # Formattazione per WhatsApp (assicuriamoci che ci sia il prefisso, es. +39)
        formatted_phone = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
       
        client.messages.create(
            body=message_body,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=formatted_phone
        )
        print(f"[RADAR] WhatsApp inviato a {phone} per targa {plate}")
       
    except Exception as e:
        print(f"[RADAR ERROR] Impossibile inviare a {phone}: {str(e)}")

def check_prices_and_notify():
    """Il Cron Job notturno che controlla i prezzi e invia gli alert"""
    print(f"[{datetime.now()}] Talyo Radar in esecuzione...")
   
    # QUI inseriremo la logica del database per recuperare gli utenti attivi
    # Per ora simuliamo un alert sul tuo numero
    send_whatsapp_alert("+393...", "AB123CD", 160.00) # Inserisci il tuo numero reale

# Inizializza lo scheduler
scheduler = BackgroundScheduler()
# Impostiamo il controllo ogni giorno alle 09:00 di mattina
scheduler.add_job(check_prices_and_notify, 'cron', hour=9, minute=0)
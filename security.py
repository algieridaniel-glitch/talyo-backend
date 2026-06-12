from cryptography.fernet import Fernet
import os

# ⚠️ QUESTA È LA CHIAVE DELLA CASSAFORTE ⚠️
# In locale usiamo questa di test. Quando andremo online su Render,
# la nasconderemo nelle variabili d'ambiente segrete.
SECRET_KEY_TEST = b'v1lRXZH_4d-t_iP7Yg9c_QkQ5m1B_u7tF-0oWwW_qgM='
chiave_attiva = os.getenv("TALYO_ENCRYPTION_KEY", SECRET_KEY_TEST)

# Inizializziamo il "Lucchetto"
lucchetto = Fernet(chiave_attiva)

def cripta_codice_fiscale(cf_in_chiaro: str) -> str:
    """Prende il CF dell'utente e lo trasforma in una stringa illeggibile per il Database"""
    cf_bytes = cf_in_chiaro.encode('utf-8')
    cf_criptato = lucchetto.encrypt(cf_bytes)
    return cf_criptato.decode('utf-8')

def decripta_codice_fiscale(cf_criptato: str) -> str:
    """Prende la stringa illeggibile dal Database e ridà a Talyo il CF reale per l'API assicurativa"""
    cf_bytes = cf_criptato.encode('utf-8')
    cf_in_chiaro = lucchetto.decrypt(cf_bytes)
    return cf_in_chiaro.decode('utf-8')
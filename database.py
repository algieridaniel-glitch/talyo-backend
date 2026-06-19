from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Configurazione del file SQLite localmente sul server
DATABASE_URL = "sqlite:///./talyo.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. La tabella delle polizze auto (Per i pagamenti futuri)
class PolizzaAutovettura(Base):
    __tablename__ = "polizze"

    id = Column(Integer, primary_key=True, index=True)
    targa = Column(String, index=True)
    codice_fiscale_criptato = Column(String)
    importo = Column(Float)
    ricevuta_stripe = Column(String, unique=True, nullable=True)
    stato_pagamento = Column(String, default="In attesa")
    data_creazione = Column(DateTime, default=datetime.utcnow)

# 3. La tabella per i dati del radar visivo (Testo grezzo fotocamera)
class ScansioneRadar(Base):
    __tablename__ = "scansioni_radar"
    
    id = Column(Integer, primary_key=True, index=True)
    targa = Column(String, index=True, nullable=False)
    testo_grezzo = Column(String, nullable=True)
    data_scansione = Column(DateTime, default=datetime.now)

# 4. NUOVA TABELLA: Cache dei Preventivi (Memoria del server)
class PreventivoCache(Base):
    __tablename__ = "preventivi_cache"

    id = Column(Integer, primary_key=True, index=True)
    targa = Column(String, unique=True, index=True, nullable=False)
    modello = Column(String)
    compagnia_attuale = Column(String)
    prezzo_min = Column(Float)
    prezzo_max = Column(Float)
    cilindrata = Column(String, nullable=True)
    data_salvataggio = Column(DateTime, default=datetime.utcnow)

# 5. Funzione di inizializzazione automatica
def inizializza_db():
    Base.metadata.create_all(bind=engine)

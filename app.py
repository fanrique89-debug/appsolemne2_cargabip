import streamlit as st
import requests
import pandas as pd
import pydeck as pdk

# ===== Configuración base =====
st.set_page_config(page_title="Puntos Bip! – Mapa simple", layout="wide")
# Evita que Streamlit muestre el stack trace gigante sobre el mapa
st.set_option("client.showErrorDetails", False)

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "cbd329c6-9fe6-4dc1-91e3-a99689fd0254"  # Recurso Puntos bip! (CKAN DataStore)

# ===================== utilidades =====================
def _guess_col(columns, *keywords):
    for c in columns:
        name = str(c).lower().strip()
        if all(k.lower() in name for k in keywords):
            return c
    return None

def _first_matching(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None

@st.cache_data(ttl=3600, show_spinner="Cargando datos desde la API…")
def fetch_all(resource_id, chunk=1000, q=None):
    params = {"resource_id": resource_id, "limit": chunk, "offset": 0}
    if q:
        params["q"] = q
    all_records = []
    while True:
        r = requests.get(API_URL, params=params, timeout=30_














import streamlit as st
import requests
import pandas as pd
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster

st.set_page_config(page_title="Puntos Bip! – Mapa simple", layout="wide")

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "cbd329c6-9fe6-4dc1-91e3-a99689fd0254"  # Recurso Puntos bip! (con DataStore CKAN)

# -------- utilidades --------
def _guess_col(columns, *keywords):
    """Retorna la primera columna cuyo nombre contenga TODOS los keywords."""
    for c in columns:
        name = str(c).lower().strip()
        if all(k.lower() in name for k in keywords):
            return c
    return None

def _first_matching(columns, candidates):
    """Primera columna de 'candidates' que exista en 'columns'."""
    for c in candidates:
        if c in columns:
            return c
    return None

@st.cache_data(ttl=3600, show_spinner="Cargando datos desde la API…")
def fetch_all(resource_id, chunk=1000, q=None):
    """Trae todos los registros con paginación desde el DataStore."""
    params = {"resource_id": resource_id, "limit": chunk, "offset": 0}
    if q:
        params["q"] = q
    all_records = []
    while True:
        r = requests.get(API_URL, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        if not js.get("success"):
            break
        result = js.get("result", {})
        records = result.get("records", [])
        all_records.extend(records)
        total = result.get("total", 0)
        if len(all_records) >= total or not records:
            break
        params["offset"] += chunk

    df = pd.DataFrame(all_records)
    df.columns = [str(c).strip() for c in df.columns]
    return df

# -------- carga de datos --------
st.title("Puntos de carga de tarjeta Bip! – Mapa")
st.caption("Fuente: datos.gob.cl · Recurso con DataStore (API CKAN)")

df = fetch_all(RESOURCE_ID)
if df.empty:
    st.error("No llegaron registros de




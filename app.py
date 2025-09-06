import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from streamlit.components.v1 import html  # encabezado sin markdown

# ================== CONFIG ==================
st.set_page_config(page_title="Puntos Bip! – Mapa simple", layout="wide")
st.set_option("client.showErrorDetails", False)

html("""
<style>
[data-testid="stNotification"]{display:none !important;}
.block-container{padding-top: 1rem;}
</style>
<div>
  <h1 style="margin:0;font-weight:700">Puntos de carga de tarjeta Bip! – Mapa con dirección</h1>
  <p style="margin:4px 0 12px;color:#6b7280">
    Fuente: datos<span>.</span>gob<span>.</span>cl · Recurso con DataStore (API CKAN)
  </p>
</div>
""", height=80)

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "cbd329c6-9fe6-4dc1-91e3-a99689fd0254"

# ===== geolocalización (opcional)
HAS_GEO = False
try:
    from streamlit_geolocation import st_geolocation  # pip install streamlit-geolocation
    HAS_GEO = True
except Exception:
    HAS_GEO = False

# ================== UTILS ==================
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
        r = requests.get(API_URL, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        if not js.get("success"):
            break
        res = js.get("result", {})
        recs = res.get("records", [])
        all_records.extend(recs)
        total = res.get("total", 0)
        if len(all_records) >= total or not recs:
            break
        params["offset"] += chunk
    df = pd.DataFrame(all_records)
    df.columns = [str(c).strip() for c in df.columns]
    return df

@st.cache_data(ttl=3600)
def geocode_address(q: str):
    if not q or len(q.strip()) < 3:
        return None
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": q, "format": "json", "limit": 1, "accept-language": "es"}
        r = requests.get(url, params=params, headers={"User-Agent": "streamlit-bip-ap

















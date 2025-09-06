import streamlit as st
import requests
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="Puntos Bip! – Mapa simple", layout="wide")

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "cbd329c6-9fe6-4dc1-91e3-a99689fd0254"  # Recurso Puntos bip! (CKAN DataStore)

# -------- utilidades --------
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

# -------- carga ----------
st.title("Puntos de carga de tarjeta Bip! – Mapa con dirección")
st.caption("Fuente: datos.gob.cl · Recurso con DataStore (API CKAN)")

df = fetch_all(RESOURCE_ID)
if df.empty:
    st.error("No llegaron registros desde la API.")
    st.stop()

# -------- detección de columnas ----------
cols = df.columns
region_col = _first_matching(cols, [c for c in cols if "regi" in str(c).lower()])
comuna_col = _first_matching(cols, [c for c in cols if "comuna" in str(c).lower()])
nombre_col = (_guess_col(cols, "nombre") or _guess_col(cols, "local")
              or _guess_col(cols, "establecimiento") or _guess_col(cols, "estaci"))
direccion_col = _guess_col(cols, "dire")
lat_col = (_guess_col(cols, "lat") or _first_matching(cols, ["Latitud", "latitud", "LATITUD"]))
lon_col = (_guess_col(cols, "lon") or _guess_col(cols, "lng") or _guess_col(cols, "long")
           or _first_matching(cols








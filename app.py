import streamlit as st
import requests
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="Puntos Bip! – Mapa simple", layout="wide")

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "cbd329c6-9fe6-4dc1-91e3-a99689fd0254"  # Recurso Puntos bip! (CKAN DataStore)

# ---------- utilidades ----------
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

# ---------- carga ----------
st.title("Puntos de carga de tarjeta Bip! – Mapa con dirección (tooltip)")
st.caption("Fuente: datos.gob.cl · Recurso con DataStore (API CKAN)")

df = fetch_all(RESOURCE_ID)
if df.empty:
    st.error("No llegaron registros desde la API.")
    st.stop()

# ---------- detección de columnas ----------
cols = df.columns
region_col = _first_matching(cols, [c for c in cols if "regi" in str(c).lower()])
comuna_col = _first_matching(cols, [c for c in cols if "comuna" in str(c).lower()])
nombre_col = (_guess_col(cols, "nombre") or _guess_col(cols, "local")
              or _guess_col(cols, "establecimiento") or _guess_col(cols, "estaci"))
direccion_col = _guess_col(cols, "dire")
lat_col = (_guess_col(cols, "lat") or _first_matching(cols, ["Latitud", "latitud", "LATITUD"]))
lon_col = (_guess_col(cols, "lon") or _guess_col(cols, "lng") or _guess_col(cols, "long")
           or _first_matching(cols, ["Longitud", "longitud", "LONGITUD"]))

# Filtrar a RM si existe
df_rm = df.copy()
if region_col and region_col in df_rm.columns:
    mask_rm = df_rm[region_col].astype(str).str.contains("metropolitana", case=False, na=False)
    if mask_rm.any():
        df_rm = df_rm[mask_rm]

# ---------- sidebar filtros ----------
st.sidebar.header("Filtros")
if comuna_col and comuna_col in df_rm.columns:
    comunas = sorted(pd.Series(df_rm[comuna_col].dropna().astype(str).unique()))
else:
    comunas = []

comunas_sel = st.sidebar.multiselect("Comunas", comunas, default=comunas[:1] if comunas else [])
texto_busqueda = st.sidebar.text_input("Buscar por nombre/dirección", placeholder="Ej: Plaza, Estación…")

# ---------- aplicar filtros ----------
df_view = df_rm.copy()
if comunas_sel and comuna_col in df_view.columns:
    df_view = df_view[df_view[comuna_col].astype(str).isin(comunas_sel)]
if texto_busqueda:
    q = texto_busqueda.strip()
    masks = []
    if nombre_col:    masks.append(df_view[nombre_col].astype(str).str.contains(q, case=False, na=False))
    if direccion_col: masks.append(df_view[direccion_col].astype(str).str.contains(q, case=False, na=False))
    if comuna_col:    masks.append(df_view[comuna_col].astype(str).str.contains(q, case=False, na=False))
    if masks:
        m = masks[0]
        for mm in masks[1:]:
            m = m | mm
        df_view = df_view[m]

st.success(f"Registros encontrados: {len(df_view):,}")

# ---------- preparar columnas para pydeck ----------
if not (lat_col and lon_col) or (lat_col not in df_view.columns or lon_col not in df_view.columns):
    st.info("No se detectaron columnas de latitud/longitud.")
    st.stop()

df_view = df_view.copy()
df_view[lat_col] = pd.to_numeric(df_view[lat_col], errors="coerce")
df_view[lon_col] = pd.to_numeric(df_view[lon_col], errors="coerce")
df_map = df_view[[lat_col, lon_col, nombre_col, direccion_col, comuna_col]].dropna(subset=[lat_col, lon_col])

if df_map.empty:
    st.info("No hay coordenadas válidas con los filtros actuales.")
    st.stop()

# Renombrar a lat/lon para pydeck y crear columna de texto para tooltip
df_map = df_map.rename(columns={lat_col: "lat", lon_col: "lon"})
df_map["__tooltip"] = (
    (df_map[nombre_col].astype(str) if nombre_col else "Punto Bip")
    + "\n"
    + (df_map[direccion_col].astype(str) if direccion_col else "Dirección no disponible")
    + ((" — " + df_map[comuna_col].astype(str)) if comuna_col else "")
)

# ---------- mapa pydeck con tooltip ----------
initial_view = pdk.ViewState(
    latitude=float(df_map["lat"].mean()),
    longitude=float(df_map["lon"].mean()),
    zoom=11,
)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_map,
    get_position='[lon, lat]',
    get_radius=60,
    pickable=True,
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=initial_view,
    tooltip={"text": "{__tooltip}"},
    map_style="mapbox://styles/mapbox/streets-v12"  # usa estilo por defecto gratuito
)

st.pydeck_chart(deck)

# ---------- listado simple (opcional) ----------
with st.expander("Ver listado (nombre + dirección)", expanded=False):
    if nombre_col and direccion_col:
        for _, row in df_map[[nombre_col, direccion_col, comuna_col]].head(150).iterrows():
            st.write(f"📍 **{row[nombre_col]}** – {row[direccion_col]} ({row[comuna_col]})")

# descarga CSV (útil para el usuario final)
st.download_button(
    "Descargar CSV filtrado",
    data=df_view.to_csv(index=False).encode("utf-8"),
    file_name="puntos_bip_filtrado.csv",
    mime="text/csv",
)






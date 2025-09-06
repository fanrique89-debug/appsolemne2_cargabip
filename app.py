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
    st.error("No llegaron registros desde la API. Intenta más tarde.")
    st.stop()

# -------- detección de columnas --------
cols = df.columns
region_col = _first_matching(cols, [c for c in cols if "regi" in str(c).lower()])
comuna_col = _first_matching(cols, [c for c in cols if "comuna" in str(c).lower()])
nombre_col = (
    _guess_col(cols, "nombre")
    or _guess_col(cols, "local")
    or _guess_col(cols, "establecimiento")
    or _guess_col(cols, "estaci")  # estación
)
direccion_col = _guess_col(cols, "dire")  # dirección
lat_col = _guess_col(cols, "lat") or _first_matching(cols, ["Latitud", "latitud", "LATITUD"])
lon_col = (
    _guess_col(cols, "lon")
    or _guess_col(cols, "lng")
    or _guess_col(cols, "long")
    or _first_matching(cols, ["Longitud", "longitud", "LONGITUD"])
)

with st.expander("Ver columnas detectadas", expanded=False):
    st.write(pd.DataFrame({
        "rol": ["región", "comuna", "nombre/local", "dirección", "latitud", "longitud"],
        "columna": [region_col, comuna_col, nombre_col, direccion_col, lat_col, lon_col],
    }))

# -------- filtro Región Metropolitana (si existe la columna) --------
df_rm = df.copy()
if region_col and region_col in df_rm.columns:
    mask_rm = df_rm[region_col].astype(str).str.contains("metropolitana", case=False, na=False)
    if mask_rm.any():
        df_rm = df_rm[mask_rm]

# -------- sidebar súper simple --------
st.sidebar.header("Filtros")
# Comunas de la RM (o todas si no hay columna región)
if comuna_col and comuna_col in df_rm.columns:
    comunas = sorted(pd.Series(df_rm[comuna_col].dropna().astype(str).unique()))
else:
    comunas = []

comunas_sel = st.sidebar.multiselect(
    "Comunas",
    comunas,
    default=comunas[:1] if comunas else []
)

texto_busqueda = st.sidebar.text_input(
    "Buscar por nombre/dirección",
    placeholder="Ej: Plaza, Estación, Mall…"
)

# -------- aplicar filtros --------
df_view = df_rm.copy()
if comunas_sel and comuna_col in df_view.columns:
    df_view = df_view[df_view[comuna_col].astype(str).isin(comunas_sel)]

if texto_busqueda:
    q = texto_busqueda.strip()
    masks = []
    if nombre_col and nombre_col in df_view.columns:
        masks.append(df_view[nombre_col].astype(str).str.contains(q, case=False, na=False))
    if direccion_col and direccion_col in df_view.columns:
        masks.append(df_view[direccion_col].astype(str).str.contains(q, case=False, na=False))
    if comuna_col and comuna_col in df_view.columns:
        masks.append(df_view[comuna_col].astype(str).str.contains(q, case=False, na=False))
    if masks:
        mask = masks[0]
        for m in masks[1:]:
            mask = mask | m
        df_view = df_view[mask]

st.success(f"Registros encontrados: {len(df_view):,}")

# -------- mapa con popups (nombre + dirección + comuna) --------
st.subheader("Mapa")
if not (lat_col and lon_col) or (lat_col not in df_view.columns or lon_col not in df_view.columns):
    st.info("No se detectaron columnas de latitud/longitud.")
    st.stop()

# coordenadas numéricas
df_view[lat_col] = pd.to_numeric(df_view[lat_col], errors="coerce")
df_view[lon_col] = pd.to_numeric(df_view[lon_col], errors="coerce")
df_map = df_view[[lat_col, lon_col, nombre_col, direccion_col, comuna_col]].dropna(subset=[lat_col, lon_col])

if df_map.empty:
    st.info("No hay coordenadas válidas con los filtros actuales.")
    st.stop()

# centro por defecto: Santiago
center_lat = float(df_map[lat_col].mean()) if not df_map.empty else -33.45
center_lon = float(df_map[lon_col].mean()) if not df_map.empty else -70.66

m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")
mc = MarkerCluster().add_to(m)

for _, r in df_map.iterrows():
    nombre = str(r[nombre_col]) if nombre_col in df_map.columns else "Punto Bip"
    direccion = str(r[direccion_col]) if direccion_col in df_map.columns else "Dirección no disponible"
    comuna = str(r[comuna_col]) if comuna_col in df_map.columns else ""
    popup_html = f"<b>{nombre}</b><br/>{direccion}<br/>{comuna}"
    folium.Marker(
        location=[float(r[lat_col]), float(r[lon_col])],
        popup=popup_html,
        tooltip=nombre  # tooltip al pasar el mouse
    ).add_to(mc)

# render del mapa en Streamlit
st_folium(m, width=None, height=600)

# -------- opcional: listado simple debajo del mapa --------
with st.expander("Ver listado (nombre + dirección)", expanded=False):
    if nombre_col and direccion_col:
        for _, row in df_map[[nombre_col, direccion_col, comuna_col]].head(150).iterrows():
            st.write(f"📍 **{row[nombre_col]}** – {row[direccion_col]} ({row[comuna_col]})")

# -------- descarga CSV filtrado (útil para usuarios) --------
st.download_button(
    "Descargar CSV filtrado",
    data=df_view.to_csv(index=False).encode("utf-8"),
    file_name="puntos_bip_filtrado.csv",
    mime="text/csv",
)





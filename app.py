import streamlit as st
import requests
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="Puntos Bip! – Mapa simple", layout="wide")

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

# ===================== UI =====================
st.title("Puntos de carga de tarjeta Bip! – Mapa con dirección")
st.caption("Fuente: datos.gob.cl · Recurso con DataStore (API CKAN)")

# “botón de pánico” para móviles antiguos
compat = st.sidebar.toggle("Modo compatibilidad (si el mapa se ve en negro)", value=False)

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
           or _first_matching(cols, ["Longitud", "longitud", "LONGITUD"]))

# -------- filtrar RM si existe ----------
df_rm = df.copy()
if region_col and region_col in df_rm.columns:
    mask_rm = df_rm[region_col].astype(str).str.contains("metropolitana", case=False, na=False)
    if mask_rm.any():
        df_rm = df_rm[mask_rm]

# -------- sidebar filtros ----------
st.sidebar.header("Filtros")
if comuna_col and comuna_col in df_rm.columns:
    comunas = sorted(pd.Series(df_rm[comuna_col].dropna().astype(str).unique()))
else:
    comunas = []

comunas_sel = st.sidebar.multiselect("Comunas", comunas, default=comunas[:1] if comunas else [])
texto_busqueda = st.sidebar.text_input("Buscar por nombre/dirección", placeholder="Ej: Plaza, Estación…")

# -------- aplicar filtros ----------
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

# Mensaje simple (sin markdown enriquecido para evitar autolink en iOS)
st.caption(f"Registros encontrados: {len(df_view)}")

# -------- preparar columnas para mapa ----------
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

# Renombrar para capas
df_map = df_map.rename(columns={lat_col: "lat", lon_col: "lon"})
df_map["__tooltip"] = (
    (df_map[nombre_col].astype(str) if nombre_col else "Punto Bip")
    + "\n"
    + (df_map[direccion_col].astype(str) if direccion_col else "Dirección no disponible")
    + ((" — " + df_map[comuna_col].astype(str)) if comuna_col else "")
)

# ===================== mapa =====================
if not compat:
    # PyDeck con ajustes para móviles
    initial_view = pdk.ViewState(
        latitude=float(df_map["lat"].mean()),
        longitude=float(df_map["lon"].mean()),
        zoom=11,
    )

    tile_layer = pdk.Layer(
        "TileLayer",
        data="https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
        minZoom=0,
        maxZoom=19,
        tileSize=256,
    )

    points_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_map,
        get_position='[lon, lat]',
        get_radius=60,
        pickable=True,
        get_fill_color=[33, 150, 243, 180],  # color fijo para evitar estilos dinámicos
    )

    deck = pdk.Deck(
        layers=[tile_layer, points_layer],
        initial_view_state=initial_view,
        map_style=None,
        tooltip={"text": "{__tooltip}"},
        height=560,  # altura fija ayuda en iOS
        parameters={
            "depthTest": False,         # reduce glitches en móviles
            "antialias": True,
        },
    )

    st.pydeck_chart(deck, use_container_width=True)
else:
    # Render simple para teléfonos “mañosos”
    df_simple = df_map.rename(columns={"lat": "latitude", "lon": "longitude"})
    st.map(df_simple[["latitude", "longitude"]], use_container_width=True, zoom=11)

# ===================== listado =====================
with st.expander("Ver listado (nombre + dirección)", expanded=False):
    if nombre_col and direccion_col:
        list_df = df_map[[nombre_col, direccion_col, comuna_col]].head(150).rename(
            columns={nombre_col: "Nombre", direccion_col: "Dirección", comuna_col: "Comuna"}
        )
        st.dataframe(list_df, use_container_width=True, hide_index=True)

# ===================== descarga =====================
st.download_button(
    "Descargar CSV filtrado",
    data=df_view.to_csv(index=False).encode("utf-8"),
    file_name="puntos_bip_filtrado.csv",
    mime="text/csv",
)












import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Puntos Bip! – RM", layout="wide")

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "cbd329c6-9fe6-4dc1-91e3-a99689fd0254"  # Puntos bip! (con DataStore)

# ---------- Utilidades ----------
def _guess_col(columns, *keywords):
    """Encuentra la primera columna cuyo nombre contenga TODOS los keywords."""
    cols_l = [c for c in columns]
    for c in cols_l:
        name = c.lower().strip()
        if all(k.lower() in name for k in keywords):
            return c
    return None

def _first_matching(columns, candidates):
    """Devuelve la primera columna que exista en 'columns' desde la lista 'candidates'."""
    for c in candidates:
        if c in columns:
            return c
    return None

@st.cache_data(ttl=3600, show_spinner="Cargando datos desde la API…")
def fetch_all(resource_id, chunk=1000, q=None):
    """
    Trae todos los registros del DataStore con paginación.
    - chunk: tamaño de página (máx típico: 32000, usamos 1000 para ir seguros)
    - q: filtro simple de CKAN (opcional)
    """
    params = {"resource_id": resource_id, "limit": chunk, "offset": 0}
    if q:
        params["q"] = q

    all_records = []
    while True:
        r = requests.get(API_URL, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()

        if not js.get("success", False):
            break

        result = js.get("result", {})
        records = result.get("records", [])
        all_records.extend(records)

        total = result.get("total", 0)
        if len(all_records) >= total or not records:
            break
        params["offset"] += chunk

    df = pd.DataFrame(all_records)
    # Normalizar nombres de columnas (sin perder los originales)
    df.columns = [c.strip() for c in df.columns]
    return df

# ---------- Carga de datos ----------
df = fetch_all(RESOURCE_ID)

st.title("Puntos de carga de tarjeta Bip! – Región Metropolitana")
st.caption("Fuente: datos.gob.cl · Recurso con DataStore (API CKAN)")

if df.empty:
    st.error("No llegaron registros desde la API. Intenta más tarde.")
    st.stop()

# ---------- Detección de columnas útiles ----------
cols = df.columns

# Región, Comuna, Nombre/local, Dirección (opcionales)
region_col = _first_matching(cols, [c for c in cols if "regi" in c.lower()])
comuna_col = _first_matching(cols, [c for c in cols if "comuna" in c.lower()])
nombre_col = (
    _guess_col(cols, "nombre") or
    _guess_col(cols, "local") or
    _guess_col(cols, "establecimiento") or
    _guess_col(cols, "estaci")
)
direccion_col = _guess_col(cols, "dire")  # direccion / dirección

# Lat/Lon (varían bastante entre datasets)
lat_col = (
    _guess_col(cols, "lat") or
    _first_matching(cols, ["Latitud", "latitud", "LATITUD"])
)
lon_col = (
    _guess_col(cols, "lon") or _guess_col(cols, "lng") or _guess_col(cols, "long") or
    _first_matching(cols, ["Longitud", "longitud", "LONGITUD"])
)

with st.expander("Ver columnas detectadas", expanded=False):
    st.write(pd.DataFrame({
        "rol": ["región", "comuna", "nombre/local", "dirección", "latitud", "longitud"],
        "columna": [region_col, comuna_col, nombre_col, direccion_col, lat_col, lon_col]
    }))

# ---------- Filtro: Región Metropolitana ----------
df_rm = df.copy()
if region_col:
    # filtra filas cuya región contenga 'Metropolitana' (case-insensitive)
    mask_rm = df_rm[region_col].astype(str).str.contains("metropolitana", case=False, na=False)
    if mask_rm.any():
        df_rm = df_rm[mask_rm]

# ---------- Sidebar de filtros ----------
st.sidebar.header("Filtros")
# Comunas disponibles (en RM si se pudo filtrar, si no, todas)
if comuna_col and comuna_col in df_rm.columns:
    comunas = sorted(pd.Series(df_rm[comuna_col].dropna().astype(str).unique()))
else:
    comunas = []

comunas_sel = st.sidebar.multiselect(
    "Comunas (RM)", comunas, default=comunas[:1] if comunas else []
)

texto_busqueda = st.sidebar.text_input(
    "Buscar por nombre/dirección", placeholder="Ej: Plaza, Estación, Mall…"
)

# ---------- Aplicar filtros ----------
df_view = df_rm.copy()

if comunas_sel and comuna_col in df_view.columns:
    df_view = df_view[df_view[comuna_col].astype(str).isin(comunas_sel)]

if texto_busqueda:
    patrones = texto_busqueda.strip()
    mask_text = pd.Series([True] * len(df_view))
    any_field = []

    if nombre_col and nombre_col in df_view.columns:
        any_field.append(df_view[nombre_col].astype(str).str.contains(patrones, case=False, na=False))
    if direccion_col and direccion_col in df_view.columns:
        any_field.append(df_view[direccion_col].astype(str).str.contains(patrones, case=False, na=False))
    if comuna_col and comuna_col in df_view.columns:
        any_field.append(df_view[comuna_col].astype(str).str.contains(patrones, case=False, na=False))

    if any_field:
        mask_text = any(any_field)
    df_view = df_view[mask_text]

st.success(f"Registros encontrados: {len(df_view):,}")

# ---------- Mapa ----------
if lat_col and lon_col and lat_col in df_view.columns and lon_col in df_view.columns:
    # asegurar numéricos
    df_view[lat_col] = pd.to_numeric(df_view[lat_col], errors="coerce")
    df_view[lon_col] = pd.to_numeric(df_view[lon_col], errors="coerce")
    mapa_df = df_view[[lat_col, lon_col]].dropna().rename(columns={lat_col: "lat", lon_col: "lon"})
    st.subheader("Mapa de puntos de carga")
    if mapa_df.empty:
        st.info("No hay coordenadas válidas para mostrar en el mapa con los filtros actuales.")
    else:
        st.map(mapa_df, zoom=10)
else:
    st.info("No se detectaron columnas de latitud/longitud para el mapa.")

# ---------- Tabla ----------
st.subheader("Tabla filtrada")
cols_tabla = [c for c in [nombre_col, direccion_col, comuna_col, region_col, lat_col, lon_col] if c]
if cols_tabla:
    st.dataframe(df_view[cols_tabla].reset_index(drop=True), use_container_width=True)
else:
    st.dataframe(df_view.head(100), use_container_width=True)

# ---------- Gráfico: conteo por comuna ----------
if comuna_col and comuna_col in df_view.columns:
    st.subheader("Puntos de carga por comuna")
    conteo = df_view[comuna_col].astype(str).value_counts().sort_values(ascending=False)
    fig, ax = plt.subplots()
    conteo.plot(kind="bar", ax=ax)
    ax.set_xlabel("Comuna")
    ax.set_ylabel("Cantidad de puntos")
    ax.set_title("Distribución de puntos de carga por comuna (filtros aplicados)")
    st.pyplot(fig)

# ---------- Descarga ----------
st.download_button(
    "Descargar CSV filtrado",
    data=df_view.to_csv(index=False).encode("utf-8"),
    file_name="puntos_bip_filtrado.csv",
    mime="text/csv",
)

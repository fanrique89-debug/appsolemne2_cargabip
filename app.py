import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# Define el resource_id del conjunto de datos que quieres analizar.
# Este es el ID que identificaste en el ejemplo.
RESOURCE_ID = 'cbd329c6-9fe6-4dc1-91e3-a99689fd0254'
API_URL = "https://datos.gob.cl/api/3/action/datastore_search"

@st.cache_data
def obtener_datos(resource_id, limit=1000):
    """
    Función para obtener datos de la API de datos.gob.cl.
    Utiliza el decorador de Streamlit para cachear los resultados y evitar
    hacer múltiples solicitudes innecesarias.
    """
    params = {'resource_id': resource_id, 'limit': limit}
    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()  # Lanza un error para códigos de estado 4xx/5xx
        data = response.json()
        
        # Verificar si la respuesta es válida y contiene datos
        if 'result' in data and 'records' in data['result']:
            return pd.DataFrame(data['result']['records'])
        else:
            st.error("Error: No se encontraron registros en la respuesta de la API.")
            return pd.DataFrame() # Retorna un DataFrame vacío
            
    except requests.exceptions.RequestException as e:
        st.error(f"Error al conectar con la API: {e}")
        return pd.DataFrame()

# Obtener los datos usando la función
df = obtener_datos(RESOURCE_ID)

# Inicia el análisis solo si el DataFrame no está vacío
if not df.empty:
    st.title("Análisis y Visualización de Datos de Chile")
    st.write("Datos obtenidos de la API de datos.gob.cl")

    # Muestra los primeros registros del DataFrame
    st.subheader("Primeros 5 registros del DataFrame")
    st.write(df.head())

    # --- Análisis y procesamiento de datos con Pandas ---
    st.subheader("Análisis de datos")

    # Ejemplo de análisis: contar valores únicos en una columna
    # Debes cambiar 'tu_columna_de_interes' por el nombre real de una columna en tu DataFrame
    # Para saber qué columnas tienes, revisa el df.head() que se muestra arriba
    try:
        if 'tu_columna_de_interes' in df.columns:
            conteo = df['tu_columna_de_interes'].value_counts()
            st.write("Conteo de valores por categoría:")
            st.write(conteo)
    except KeyError:
        st.warning("La columna 'tu_columna_de_interes' no fue encontrada. Por favor, actualiza el nombre de la columna en el código.")
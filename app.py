import streamlit as st
import requests
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Predicciones Prode", page_icon="⚽", layout="centered")

# Clave de API (idealmente guardada en los secrets de Streamlit)
API_KEY = 'TU_CLAVE_DE_API_AQUI' 
# Usamos la liga argentina para testear ahora, en el mundial será 'soccer_fifa_world_cup'
SPORT = 'soccer_argentina_primera_division' 
MARKETS = 'correct_score'
REGIONS = 'eu' # Usamos casas de apuestas europeas/globales por su liquidez

@st.cache_data(ttl=3600) # Guarda en caché los datos por 1 hora para no gastar cuota de la API
def obtener_predicciones():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {
        'apiKey': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': 'decimal'
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None
    
    data = response.json()
    partidos_procesados = []

    # Procesamos el JSON para encontrar el resultado más probable
    for partido in data:
        equipo_local = partido['home_team']
        equipo_visitante = partido['away_team']
        fecha = partido['commence_time'][:10]
        
        # Tomamos solo la primera casa de apuestas disponible para simplificar
        if partido['bookmakers']:
            apuestas = partido['bookmakers'][0]['markets'][0]['outcomes']
            
            # Encontramos la cuota mínima (min price)
            resultado_mas_probable = min(apuestas, key=lambda x: x['price'])
            
            partidos_procesados.append({
                "Fecha": fecha,
                "Partido": f"{equipo_local} vs {equipo_visitante}",
                "Predicción (Goles)": resultado_mas_probable['name'],
                "Cuota (Probabilidad)": resultado_mas_probable['price']
            })
            
    return pd.DataFrame(partidos_procesados)

# --- INTERFAZ DE LA APP ---
st.title("⚽ Predictor de Resultados Exactos")
st.write("Basado en el consenso de las casas de apuestas (Cuota más baja).")

if st.button("Actualizar Predicciones"):
    with st.spinner('Consultando algoritmos de apuestas...'):
        df = obtener_predicciones()
        
        if df is not None and not df.empty:
            st.success("¡Datos actualizados!")
            # Mostramos la tabla optimizada para la vista del celular
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.error("Hubo un error al conectar con la API o no hay partidos disponibles.")

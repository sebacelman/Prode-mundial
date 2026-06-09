import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Predicciones Prode Mundial", page_icon="⚽", layout="wide")

API_KEY = 'a9b7c4446ff19f47b711aea2ac633e5a' 
SPORT = 'soccer_fifa_world_cup' 
MARKETS = 'h2h,totals' # Pedimos ganador del partido y total de goles
REGIONS = 'eu' 

@st.cache_data(ttl=3600)
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
        st.error(f"🚨 Error de conexión. Código: {response.status_code}")
        st.json(response.json())
        return None
    
    data = response.json()
    
    if not data:
        st.warning("⚠️ No hay partidos disponibles para la liga seleccionada.")
        return pd.DataFrame()
        
    partidos_procesados = []
    
    ahora = datetime.now(timezone.utc)
    proxima_semana = ahora + timedelta(days=7)

    for partido in data:
        fecha_str = partido['commence_time']
        fecha_partido = datetime.strptime(fecha_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        
        if ahora <= fecha_partido <= proxima_semana:
            equipo_local = partido['home_team']
            equipo_visitante = partido['away_team']
            
            if partido['bookmakers']:
                mercados = partido['bookmakers'][0]['markets']
                
                # Buscamos los datos de H2H y Totals en la respuesta
                h2h_outcomes = next((m['outcomes'] for m in mercados if m['key'] == 'h2h'), None)
                totals_outcomes = next((m['outcomes'] for m in mercados if m['key'] == 'totals'), None)
                
                # Solo procesamos si la casa de apuestas tiene ambos mercados publicados
                if h2h_outcomes and totals_outcomes:
                    # 1. ¿Quién gana? (Menor cuota)
                    resultado_match = min(h2h_outcomes, key=lambda x: x['price'])
                    ganador = resultado_match['name']
                    
                    # 2. ¿Muchos o pocos goles? (Menor cuota)
                    resultado_goles = min(totals_outcomes, key=lambda x: x['price'])
                    es_under = 'Under' in resultado_goles['name']
                    
                    # 3. Motor de inferencia de resultado exacto para el Prode
                    prediccion_score = ""
                    if ganador == equipo_local:
                        prediccion_score = "1-0" if es_under else "2-1"
                    elif ganador == equipo_visitante:
                        prediccion_score = "0-1" if es_under else "1-2"
                    else: # Empate
                        prediccion_score = "1-1" if es_under else "2-2"
                        
                    partidos_procesados.append({
                        "Fecha": fecha_partido.strftime("%d/%m %H:%M"),
                        "Partido": f"{equipo_local} vs {equipo_visitante}",
                        "Ganador": ganador,
                        "Tendencia Goles": resultado_goles['name'],
                        "Predicción Prode": prediccion_score
                    })
            
    if not partidos_procesados:
        st.info("No hay partidos con cuotas completas en los próximos 7 días.")
        return pd.DataFrame()
            
    return pd.DataFrame(partidos_procesados)

# --- INTERFAZ DE LA APP ---
st.title("🏆 Predictor Mundial 2026")
st.write("Generación de resultados matemáticos cruzando Ganador + Línea de Goles.")

if st.button("Actualizar Predicciones"):
    with st.spinner('Consultando cuotas y calculando heurística...'):
        df = obtener_predicciones()
        
        if df is not None and not df.empty:
            st.success("¡Datos actualizados!")
            st.dataframe(df, use_container_width=True, hide_index=True)

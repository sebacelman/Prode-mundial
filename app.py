import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Prode Mundial 2026", page_icon="⚽", layout="centered")

# --- SECRETS Y CLAVES ---
API_KEY_ODDS = 'a9b7c4446ff19f47b711aea2ac633e5a' 
JSONBIN_BIN_ID = st.secrets["JSONBIN_BIN_ID"]
JSONBIN_KEY = st.secrets["JSONBIN_KEY"]
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

SPORT = 'soccer_fifa_world_cup' 
MARKETS = 'h2h,totals' 
REGIONS = 'eu' 

# --- CONEXIÓN CON JSONBIN (NUBE) ---
def cargar_predicciones_nube():
    headers = {'X-Master-Key': JSONBIN_KEY}
    try:
        response = requests.get(JSONBIN_URL, headers=headers)
        if response.status_code == 200:
            return response.json().get('record', {})
    except:
        pass
    return {}

def guardar_prediccion_nube(id_partido, marcador):
    estado_actual = cargar_predicciones_nube()
    estado_actual[str(id_partido)] = str(marcador)
    headers = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_KEY}
    requests.put(JSONBIN_URL, json=estado_actual, headers=headers)
    st.session_state['predicciones'][str(id_partido)] = marcador

# --- MOTOR HEURÍSTICO DINÁMICO AVANZADO ---
def calcular_marcador_inteligente(ganador, cuota_ganador, equipo_local, equipo_visitante, tendencia_goles_str):
    if not tendencia_goles_str:
        es_under = True
        linea_numerica = 2.5
    else:
        partes = tendencia_goles_str.split()
        es_under = "Under" in partes[0]
        linea_numerica = float(partes[1]) if len(partes) > 1 else 2.5

    # NUEVO: Evaluamos si el ganador es un favorito aplastante (cuota menor a 1.55)
    es_goleada = cuota_ganador < 1.55

    if ganador not in [equipo_local, equipo_visitante]:
        if es_under: return "0-0" if linea_numerica < 2.0 else "1-1"
        else: return "2-2" if linea_numerica < 4.0 else "3-3"

    # NUEVO: Lógica sensible al favoritismo
    if es_under:
        if linea_numerica <= 1.5: 
            goles_ganador, goles_perdedor = 1, 0
        elif linea_numerica <= 2.5: 
            goles_ganador, goles_perdedor = 2, 0
        elif linea_numerica <= 3.5: 
            goles_ganador, goles_perdedor = (3, 0) if es_goleada else (2, 1)
        else: 
            goles_ganador, goles_perdedor = (4, 0) if es_goleada else (3, 1)
    else: # Es Over
        if linea_numerica <= 1.5: 
            goles_ganador, goles_perdedor = (3, 0) if es_goleada else (2, 0)
        elif linea_numerica <= 2.5: 
            goles_ganador, goles_perdedor = (3, 0) if es_goleada else (2, 1) # ¡Acá está la magia del 3-0!
        elif linea_numerica <= 3.5: 
            goles_ganador, goles_perdedor = (4, 0) if es_goleada else (3, 1)
        else: 
            goles_ganador, goles_perdedor = (5, 0) if es_goleada else (3, 2)

    if ganador == equipo_local:
        return f"{goles_ganador}-{goles_perdedor}"
    else:
        return f"{goles_perdedor}-{goles_ganador}"

# --- TRATAMIENTO DE DATOS DE THE ODDS API ---
@st.cache_data(ttl=3600)
def obtener_partidos_api():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {'apiKey': API_KEY_ODDS, 'regions': REGIONS, 'markets': MARKETS, 'oddsFormat': 'decimal'}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return []

if 'predicciones' not in st.session_state:
    st.session_state['predicciones'] = cargar_predicciones_nube()

st.title("🏆 Predictor Prode 3.0")
st.write("Motor heurístico dinámico con sensibilidad de goleadas.")

if st.button("🔄 Sincronizar Fixture (Próximos 15 días)"):
    st.cache_data.clear()
    st.session_state['predicciones'] = cargar_predicciones_nube()
    st.rerun()

datos_api = obtener_partidos_api()

if datos_api:
    ahora = datetime.now(timezone.utc)
    proximos_15_dias = ahora + timedelta(days=15)
    partidos_encontrados = False

    for partido in datos_api:
        id_partido = str(partido['id'])
        fecha_partido = datetime.strptime(partido['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        
        if ahora <= fecha_partido <= proximos_15_dias:
            partidos_encontrados = True
            equipo_local = partido['home_team']
            equipo_visitante = partido['away_team']
            fecha_formateada = fecha_partido.strftime("%d/%m %H:%M")
            
            with st.container(border=True):
                st.markdown(f"**📅 {fecha_formateada}**")
                st.subheader(f"{equipo_local} vs {equipo_visitante}")
                
                prediccion_actual = st.session_state['predicciones'].get(id_partido, "Sin predecir")
                
                if prediccion_actual != "Sin predecir":
                    st.success(f"📝 Pronóstico guardado: **{prediccion_actual}**")
                else:
                    st.info("📝 Estado: Sin predecir")
                
                if st.button(f"🔮 Calcular y guardar", key=f"btn_{id_partido}"):
                    if partido['bookmakers']:
                        h2h = None
                        totals = None
                        nombre_casa = "Desconocida"
                        
                        for bookmaker in partido['bookmakers']:
                            mercados = bookmaker['markets']
                            h2h_temp = next((m['outcomes'] for m in mercados if m['key'] == 'h2h'), None)
                            totals_temp = next((m['outcomes'] for m in mercados if m['key'] == 'totals'), None)
                            
                            if h2h_temp and totals_temp:
                                h2h = h2h_temp
                                totals = totals_temp
                                nombre_casa = bookmaker['title']
                                break 
                        
                        if not h2h:
                            for bookmaker in partido['bookmakers']:
                                mercados = bookmaker['markets']
                                h2h_temp = next((m['outcomes'] for m in mercados if m['key'] == 'h2h'), None)
                                if h2h_temp:
                                    h2h = h2h_temp
                                    nombre_casa = bookmaker['title']
                                    break
                        
                        if h2h:
                            # 1. Obtenemos al ganador y su cuota
                            resultado_ganador = min(h2h, key=lambda x: x['price'])
                            ganador_nombre = resultado_ganador['name']
                            ganador_cuota_valor = resultado_ganador['price']
                            
                            # 2. Obtenemos el texto completo de los goles
                            tendencia_goles_str = None
                            origen_dato = "🛡️ (Respaldo)"
                            if totals:
                                resultado_goles = min(totals, key=lambda x: x['price'])
                                tendencia_goles_str = resultado_goles['name']
                                origen_dato = f"🎯 (Apuestas: {tendencia_goles_str})"
                            
                            # 3. Pasamos el ganador, la cuota y los goles por el motor
                            marcador_base = calcular_marcador_inteligente(
                                ganador_nombre, 
                                ganador_cuota_valor, 
                                equipo_local, 
                                equipo_visitante, 
                                tendencia_goles_str
                            )
                            
                            # Añadimos un ícono de 🔥 si detectó goleada para que lo sepas
                            if ganador_cuota_valor < 1.55 and (tendencia_goles_str and "Over" in tendencia_goles_str):
                                marcador_base = f"🔥 {marcador_base}"

                            marcador_final = f"{marcador_base} | {origen_dato} | 🏦 {nombre_casa}"
                            
                            with st.spinner('Procesando heurística y guardando...'):
                                guardar_prediccion_nube(id_partido, marcador_final)
                            st.rerun()
                        else:
                            st.warning("No se encontraron cuotas base para este encuentro.")
                    else:
                        st.warning("No hay cuotas disponibles aún para este partido.")
                        
    if not partidos_encontrados:
        st.info("No hay partidos en los próximos 15 días.")
else:
    st.error("Error al conectar con la API de cuotas.")

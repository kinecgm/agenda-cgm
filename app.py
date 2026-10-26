import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials
import json
import time
import calendar
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_geolocation import streamlit_geolocation

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Agenda Kinesiología CGM", page_icon="📅", layout="wide")

# --- ESTILOS PERSONALIZADOS Y RESPONSIVOS (MOBILE FIX DEFINITIVO + THICK FONT + FANTASMAS) ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .titulo-principal { color: #2C3E50; text-align: center; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 800; font-size: 2.5rem; margin-bottom: -10px; }
    .subtitulo { color: #18BC9C; text-align: center; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 600; font-size: 1.2rem; margin-bottom: 2rem; }
    
    /* Configuración por defecto para PC de la cuadrícula de 7 columnas */
    div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button {
        width: 100% !important; padding: 12px 0px !important; border-radius: 8px !important;
        font-size: 1rem !important; font-weight: 900 !important; box-shadow: 0px 1px 3px rgba(0,0,0,0.1) !important;
        border: 1px solid #E0E6ED !important; min-height: 45px !important;
    }
    
    /* Forzar el grosor del texto dentro del botón del calendario sin bloquear el color */
    div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button p,
    div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button strong {
        font-weight: 900 !important;
        font-size: 1.2rem !important;
    }
    
    /* MAGIA PARA ALINEAR LA GRILLA: Ocultar los botones "fantasma" de los días vacíos */
    div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button[disabled] {
        opacity: 0 !important;
        pointer-events: none !important;
    }
    
    /* MAGIA PARA CELULARES (VERTICAL) */
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) {
            display: grid !important; grid-template-columns: repeat(7, 1fr) !important; gap: 4px !important; width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) > div[data-testid="column"] {
            width: 100% !important; min-width: 0 !important; padding: 0 !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button {
            padding: 0px !important; min-height: 45px !important; border-radius: 6px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button p,
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button strong {
            font-size: 1.25rem !important; font-weight: 900 !important; margin: 0 !important; 
            overflow: visible !important; text-overflow: clip !important; white-space: normal !important;
        }
        
        .dia-semana { font-size: 0.8rem !important; }
        .titulo-principal { font-size: 1.8rem !important; }
        .subtitulo { font-size: 1rem !important; margin-bottom: 1rem !important; }
    }
    button[data-baseweb="tab"] { font-size: 1rem !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="titulo-principal">Centro de Comando</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitulo">Kinesiología CGM — Orden y Planificación</p>', unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE SHEETS Y CALENDAR ---
@st.cache_resource
def conectar_bd():
    credenciales_json = json.loads(st.secrets["gcp_credentials"], strict=False)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets", 
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/calendar.events"
    ]
    creds = Credentials.from_service_account_info(credenciales_json, scopes=scopes)
    cliente = gspread.authorize(creds)
    
    doc_kine = cliente.open_by_url("https://docs.google.com/spreadsheets/d/1UWyFJrlYcP_PK4fVYVPxbARIobNl4p8DuQ8OgyNU6aA/edit")
    
    return doc_kine, creds

try: 
    doc, credenciales_gcp = conectar_bd()
except Exception as e:
    st.error(f"🚨 Error conectando credenciales: {e}")
    st.stop()

def obtener_hoja(nombre):
    try: return doc.worksheet(nombre)
    except gspread.exceptions.WorksheetNotFound: return doc.add_worksheet(title=nombre, rows="1000", cols="20")

@st.cache_data(ttl=60)
def cargar_tabla(nombre_hoja):
    try:
        hoja = obtener_hoja(nombre_hoja)
        datos = hoja.get_all_records()
        return pd.DataFrame(datos) if datos else pd.DataFrame()
    except Exception as e:
        st.cache_data.clear() 
        st.error(f"🚨 Error de Google (Lectura): {e}")
        st.stop() 

def guardar_tabla(nombre_hoja, df):
    hoja = obtener_hoja(nombre_hoja)
    hoja.clear()
    if not df.empty:
        df_limpio = df.fillna("").astype(str)
        hoja.update([df_limpio.columns.values.tolist()] + df_limpio.values.tolist())
    st.cache_data.clear()

def parse_dinero(val):
    try:
        if pd.isna(val): return 0.0
        s = str(val).strip()
        if s in ["", "nan", "NaN", "-"]: return 0.0
        s = s.replace('$', '')
        if s.endswith('.0'): s = s[:-2] 
        s = s.replace('.', '').replace(',', '')
        v = float(s)
        if 0 < v < 1000: return v * 1000
        return v
    except:
        return 0.0

# --- CÁLCULO DE IMPUESTOS SII CHILE LEY 21.133 ---
def obtener_tasa_sii(anio):
    tasas = {
        2024: 0.1375, 
        2025: 0.1450, 
        2026: 0.1525, 
        2027: 0.1600, 
    }
    if anio < 2024: return 0.13
    if anio >= 2028: return 0.17
    return tasas.get(anio, 0.1525)

# --- MEMORIA Y NAVEGACIÓN ---
if "app_fecha_sel" not in st.session_state: st.session_state.app_fecha_sel = date.today()
if "app_vista" not in st.session_state: st.session_state.app_vista = "calendario"
if "app_mes_cal" not in st.session_state: st.session_state.app_mes_cal = date.today().replace(day=1)

def ir_a_hoy():
    st.session_state.app_fecha_sel = date.today()
    st.session_state.app_mes_cal = date.today().replace(day=1)
    st.session_state.app_vista = "dia"

def cambiar_mes(delta):
    mes = st.session_state.app_mes_cal.month - 1 + delta
    año = st.session_state.app_mes_cal.year + mes // 12
    mes = mes % 12 + 1
    st.session_state.app_mes_cal = date(año, mes, 1)

# --- RUTAS PRINCIPALES ---
if st.session_state.app_vista == "calendario":
    col_mes1, col_mes2, col_mes3 = st.columns([1, 2, 1])
    with col_mes1: st.button("⬅️ Ant", on_click=cambiar_mes, args=(-1,), use_container_width=True)
    with col_mes2:
        meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        año_act = st.session_state.app_mes_cal.year
        mes_act = st.session_state.app_mes_cal.month
        st.markdown(f"<h3 style='text-align: center; color: #2C3E50; margin-top: 0;'>{meses_es[mes_act-1]} {año_act}</h3>", unsafe_allow_html=True)
    with col_mes3: st.button("Sig ➡️", on_click=cambiar_mes, args=(1,), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    dias_semana = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
    cols_dias = st.columns(7)
    for i, d in enumerate(dias_semana):
        cols_dias[i].markdown(f"<div class='dia-semana' style='text-align:center; font-weight:700; color:#18BC9C; padding-bottom: 5px;'>{d}</div>", unsafe_allow_html=True)

    # --- LÓGICA DE RADAR DE PACIENTES PARA EL CALENDARIO ---
    df_clinica_cal = cargar_tabla("Clinica")
    mapa_pacientes_cal = {}
    mapa_nombres_cal = {}
    
    if not df_clinica_cal.empty and 'Fecha' in df_clinica_cal.columns:
        df_validos = df_clinica_cal[
            (df_clinica_cal['Paciente'].astype(str).str.strip() != "") &
            (df_clinica_cal['Paciente'].astype(str).str.strip().str.upper() != "ALMUERZO") &
            (~df_clinica_cal['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))
        ].copy()
        
        conteos = df_validos.groupby('Fecha').size().to_dict()
        mapa_pacientes_cal = conteos
        
        df_validos['Hora_limpia'] = df_validos['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip()
        df_validos = df_validos.sort_values(by=['Fecha', 'Hora_limpia'])
        
        for f, df_f in df_validos.groupby('Fecha'):
            lista_pacs = []
            for _, r in df_f.iterrows():
                hora_corta = r['Hora_limpia']
                paciente_corto = str(r['Paciente']).strip()
                lista_pacs.append(f"⏱ {hora_corta} - {paciente_corto}")
            # Un salto de línea simple asegura que el tooltip en Mac se vea perfecto
            mapa_nombres_cal[f] = "\n".join(lista_pacs)

    cal = calendar.monthcalendar(año_act, mes_act)
    for week_idx, week in enumerate(cal):
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                fecha_iter_str = f"{año_act}-{mes_act:02d}-{day:02d}"
                cant_pacs = mapa_pacientes_cal.get(fecha_iter_str, 0)
                detalle_dia = mapa_nombres_cal.get(fecha_iter_str, "Día libre 🟢")
                is_today = (date.today() == date(año_act, mes_act, day))
                
                # APLICACIÓN DE COLORES NATIVOS MARKDOWN
                if is_today:
                    texto_boton = f"**{day}**"
                else:
                    if cant_pacs == 0: texto_boton = f":green[**{day}**]"
                    elif cant_pacs == 1: texto_boton = f":blue[**{day}**]"
                    elif cant_pacs == 2: texto_boton = f":orange[**{day}**]"
                    else: texto_boton = f":red[**{day}**]"

                btn_type = "primary" if is_today else "secondary"

                if cols[i].button(texto_boton, key=f"d_{año_act}_{mes_act}_{day}", help=detalle_dia, use_container_width=True, type=btn_type):
                    st.session_state.app_fecha_sel = date(año_act, mes_act, day)
                    st.session_state.app_vista = "dia"
                    st.rerun()
            else: 
                # EL BOTÓN FANTASMA QUE ALINEA LA GRILLA PERFECTAMENTE
                cols[i].button(" ", key=f"empty_{año_act}_{mes_act}_{week_idx}_{i}", disabled=True, help="", use_container_width=True)

    # Leyenda visual renovada
    st.markdown("""
    <div style='text-align: center; font-size: 0.9rem; font-weight: bold; color: #7f8c8d; margin-top: 15px;'>
        <span style='color: #2ecc71;'>●</span> Libre &nbsp;|&nbsp; 
        <span style='color: #3498db;'>●</span> 1 Paciente &nbsp;|&nbsp; 
        <span style='color: #ff9f43;'>●</span> 2 Pacientes &nbsp;|&nbsp; 
        <span style='color: #e74c3c;'>●</span> 3+ Pacientes
    </div>
    """, unsafe_allow_html=True)
    
    # --- PANEL MÓVIL: RESUMEN RÁPIDO CON HTML ALINEADO PERFECTAMENTE ---
    st.markdown("<hr style='margin: 15px 0px;'>", unsafe_allow_html=True)
    with st.expander("📱 Resumen de Pacientes (Vista Celular)"):
        cal_semanas = calendar.monthcalendar(año_act, mes_act)
        nombres_tabs = []
        for i, semana in enumerate(cal_semanas):
            dias_reales = [d for d in semana if d != 0]
            if dias_reales:
                nombres_tabs.append(f"Sem {i+1} ({dias_reales[0]}-{dias_reales[-1]})")
            
        tabs_semanas = st.tabs(nombres_tabs)
        
        for i, semana in enumerate(cal_semanas):
            with tabs_semanas[i]:
                hay_pacientes_semana = False
                for day in semana:
                    if day != 0:
                        fecha_str_semana = f"{año_act}-{mes_act:02d}-{day:02d}"
                        if fecha_str_semana in mapa_nombres_cal:
                            # Título del día
                            st.markdown(f"<p style='margin-bottom: 4px; font-weight: 800; font-size: 1.05rem; color: #2C3E50;'>Día {day}</p>", unsafe_allow_html=True)
                            
                            # Separamos los pacientes línea por línea
                            lineas_pacientes = mapa_nombres_cal[fecha_str_semana].split('\n')
                            
                            # Construimos una caja HTML limpia para garantizar alineación perfecta a la izquierda
                            caja_html = "<div style='background-color: #f0f4f8; border-left: 4px solid #18BC9C; padding: 12px 16px; border-radius: 0px 8px 8px 0px; margin-bottom: 20px; box-shadow: 0px 1px 2px rgba(0,0,0,0.05);'>"
                            for linea in lineas_pacientes:
                                caja_html += f"<div style='color: #34495E; font-size: 0.95rem; margin-bottom: 6px; font-weight: 500; display: flex; align-items: center;'>{linea}</div>"
                            caja_html += "</div>"
                            
                            st.markdown(caja_html, unsafe_allow_html=True)
                            hay_pacientes_semana = True
                
                if not hay_pacientes_semana:
                    st.info("No hay pacientes agendados para esta semana. ¡A descansar! 🟢")

    st.button("🎯 Ir directamente a la agenda de Hoy", on_click=ir_a_hoy, use_container_width=True, type="primary")

else:
    col_back, col_vacia, col_hoy = st.columns([1, 2, 1])
    with col_back:
        if st.button("📅 Volver al Mes", use_container_width=True):
            st.session_state.app_vista = "calendario"
            st.rerun()
    with col_hoy: st.button("🎯 Ir a Hoy", on_click=ir_a_hoy, use_container_width=True)

    fecha_str = st.session_state.app_fecha_sel.strftime("%Y-%m-%d")
    fecha_visual = st.session_state.app_fecha_sel.strftime("%d/%m/%Y")
    horas_30_min = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00"]
    es_hoy = (st.session_state.app_fecha_sel == date.today())

    def guardar_dia(tipo, fecha, df_dia):
        df_guardar = df_dia.copy()
        if 'Hora' in df_guardar.columns:
            df_guardar['Hora'] = df_guardar['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip()
            
        df_guardar.insert(0, 'Fecha', fecha)
        try:
            hoja_segura = obtener_hoja(tipo)
            datos_seguros = hoja_segura.get_all_records()
            df_completo = pd.DataFrame(datos_seguros) if datos_seguros else pd.DataFrame()
        except Exception as e:
            st.error(f"🚨 Error real de Google (Escritura): {e}")
            return False 
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_completo = df_completo[df_completo['Fecha'] != fecha]
            df_final = pd.concat([df_completo, df_guardar], ignore_index=True)
        else:
            df_final = df_guardar
        guardar_tabla(tipo, df_final)
        return True 

    # --- FUNCIONES BASE ---
    def cargar_datos_clinica(fecha):
        df_completo = cargar_tabla("Clinica")
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_dia = df_completo[df_completo['Fecha'] == fecha]
            if not df_dia.empty: 
                if 'Abono ($)' not in df_dia.columns: df_dia['Abono ($)'] = ""
                if 'Boleta' not in df_dia.columns: df_dia['Boleta'] = "-"
                return df_dia.drop(columns=['Fecha']).reset_index(drop=True)
        return pd.DataFrame({
            "Hora": horas_30_min, "Paciente": [""] * len(horas_30_min), "Detalle / Motivo": [""] * len(horas_30_min),
            "Dirección": [""] * len(horas_30_min), "Minutos de Viaje": [0] * len(horas_30_min), 
            "Hora de Salida": [""] * len(horas_30_min), "Ruta Maps": [""] * len(horas_30_min), "Alarma": [""] * len(horas_30_min),
            "Estado": ["Libre 🟢"] * len(horas_30_min), "N° Sesión": [""] * len(horas_30_min), "Pago": ["-"] * len(horas_30_min),
            "Abono ($)": [""] * len(horas_30_min), "Boleta": ["-"] * len(horas_30_min), "Recordatorio": [""] * len(horas_30_min)
        })

    def cargar_datos_personal(fecha):
        df_completo = cargar_tabla("Personal")
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_dia = df_completo[df_completo['Fecha'] == fecha]
            if not df_dia.empty: return df_dia.drop(columns=['Fecha']).reset_index(drop=True)
        return pd.DataFrame({"Hora": horas_30_min, "Actividad": [""] * len(horas_30_min), "Categoría": ["-"] * len(horas_30_min), "Notas": [""] * len(horas_30_min)})

    def obtener_actividad_por_hora(df_personal):
        if df_personal.empty or 'Hora' not in df_personal.columns: return {}
        clean_hora = df_personal['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip()
        return dict(zip(clean_hora, df_personal['Actividad'].astype(str).str.strip()))

    def calcular_tiempo_gps(origen_coords_o_texto, destino):
        try:
            geolocator = Nominatim(user_agent="kine_agenda_gps", timeout=5)
            if isinstance(origen_coords_o_texto, tuple): coords_1 = origen_coords_o_texto 
            else:
                loc_origen = geolocator.geocode(origen_coords_o_texto + ", Valparaiso, Chile")
                if not loc_origen: return 0
                coords_1 = (loc_origen.latitude, loc_origen.longitude)
            loc_destino = geolocator.geocode(destino + ", Valparaiso, Chile")
            if loc_destino:
                coords_2 = (loc_destino.latitude, loc_destino.longitude)
                distancia_km = geodesic(coords_1, coords_2).kilometers
                minutos_estimados = int((distancia_km * 2.5) + 5)
                return minutos_estimados
        except Exception: pass
        return 0

    def obtener_lista_pacientes():
        pacientes = set()
        df_clinica = cargar_tabla("Clinica")
        if not df_clinica.empty and 'Paciente' in df_clinica.columns:
            for p in df_clinica['Paciente'].dropna().unique():
                p_str = str(p).strip()
                if p_str != "" and p_str.upper() != "ALMUERZO": pacientes.add(p_str.title()) 
        
        df_fichas = cargar_tabla("Fichas")
        if not df_fichas.empty and 'Paciente' in df_fichas.columns:
            for p in df_fichas['Paciente'].dropna().unique():
                p_str = str(p).strip()
                if p_str != "": pacientes.add(p_str.title()) 
                
        return sorted(list(pacientes))

    def calcular_estadisticas_globales(nombre_paciente):
        nombre_norm = str(nombre_paciente).strip().upper()
        df_completo = cargar_tabla("Clinica")
        if df_completo.empty or 'Paciente' not in df_completo.columns: return 0, 0, 0
        df_pac = df_completo[(df_completo['Paciente'].str.strip().str.upper() == nombre_norm) & (~df_completo['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))]
        tot_sesiones = len(df_pac)
        pagadas = len(df_pac[df_pac['Pago'].isin(["Pagada ✅", "Saldada con Billetera ✅", "Pagada con Billetera ✅", "Pagada (Excedente) ✅"])])
        adeudadas = len(df_pac[df_pac['Pago'].isin(["No pagada ❌", "Abono Parcial ⏳"])])
        return tot_sesiones, pagadas, adeudadas

    def obtener_telefono_por_paciente():
        df_fichas = cargar_tabla("Fichas")
        if df_fichas.empty or 'Paciente' not in df_fichas.columns or 'Teléfono' not in df_fichas.columns: return {}
        return dict(zip(df_fichas['Paciente'].astype(str).str.strip().str.upper(), df_fichas['Teléfono'].astype(str).str.strip()))
        
    def obtener_direccion_por_paciente():
        df_fichas = cargar_tabla("Fichas")
        if df_fichas.empty or 'Paciente' not in df_fichas.columns or 'Dirección' not in df_fichas.columns: return {}
        return dict(zip(df_fichas['Paciente'].astype(str).str.strip().str.upper(), df_fichas['Dirección'].astype(str).str.strip()))

    def obtener_valor_por_paciente():
        df_fichas = cargar_tabla("Fichas")
        if df_fichas.empty or 'Paciente' not in df_fichas.columns or 'Valor Sesión' not in df_fichas.columns: return {}
        mapa = {}
        for nombre, valor in zip(df_fichas['Paciente'].astype(str).str.strip().str.upper(), df_fichas['Valor Sesión']):
            mapa[nombre] = parse_dinero(valor)
        return mapa

    def obtener_valor_pauta_por_paciente():
        df_fichas = cargar_tabla("Fichas")
        if df_fichas.empty or 'Paciente' not in df_fichas.columns or 'Valor Pauta' not in df_fichas.columns: return {}
        mapa = {}
        for nombre, valor in zip(df_fichas['Paciente'].astype(str).str.strip().str.upper(), df_fichas['Valor Pauta']):
            mapa[nombre] = parse_dinero(valor)
        return mapa

    def construir_link_whatsapp(telefono, fecha_visual_str, hora_str):
        if not telefono or str(telefono).strip() == "": return ""
        solo_digitos = "".join(ch for ch in str(telefono) if ch.isdigit())
        if solo_digitos == "": return ""
        if not solo_digitos.startswith("56"): solo_digitos = "56" + solo_digitos.lstrip("0")
        mensaje = f"Hola, ¿qué tal? Quería confirmar la sesión agendada para el {fecha_visual_str} a las {hora_str} hrs. Cualquier cosa me avisas 🙂"
        texto_codificado = urllib.parse.quote(mensaje)
        return f"https://wa.me/{solo_digitos}?text={texto_codificado}"

    def calcular_dashboard_mensual(fecha_referencia):
        df_completo = cargar_tabla("Clinica")
        resultado = {
            "total_sesiones": 0, "pagadas": 0, "adeudadas": 0, 
            "ingresos": 0.0, "por_cobrar": 0.0, 
            "ingresos_sesiones": 0.0, "ingresos_pautas": 0.0,
            "deuda_sesiones": 0.0, "deuda_pautas": 0.0,
            "pacientes_con_deuda": 0, "pacientes_totales": 0,
            "ingresos_boleta": 0.0
        }
        if df_completo.empty or 'Fecha' not in df_completo.columns: return resultado
        prefijo_mes = fecha_referencia.strftime("%Y-%m")
        df_mes = df_completo[df_completo['Fecha'].astype(str).str.startswith(prefijo_mes)].copy()
        df_mes = df_mes[~df_mes['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"])]
        df_mes = df_mes[(df_mes['Paciente'].astype(str).str.strip() != "") & (df_mes['Paciente'].astype(str).str.strip().str.upper() != "ALMUERZO")]
        if df_mes.empty: return resultado
        
        mapa_valores = obtener_valor_por_paciente()
        mapa_pautas = obtener_valor_pauta_por_paciente()
        df_mes['Paciente_norm'] = df_mes['Paciente'].astype(str).str.strip().str.upper()
        if 'Abono ($)' not in df_mes.columns: df_mes['Abono ($)'] = ""
        if 'Boleta' not in df_mes.columns: df_mes['Boleta'] = "-"
        
        for index, row in df_mes.iterrows():
            pac_norm = row['Paciente_norm']
            es_pauta = (str(row['Detalle / Motivo']).strip() == "Pauta Online 💻")
            val_sesion = mapa_pautas.get(pac_norm, 0.0) if es_pauta else mapa_valores.get(pac_norm, 0.0)
            
            pago_estado = str(row['Pago']).strip()
            abono_val = parse_dinero(row['Abono ($)'])
            boleta_estado = str(row['Boleta']).strip()
            
            ingreso_hoy = 0.0
            deuda_hoy = 0.0
            pagada_count = 0
            adeudada_count = 0
            
            if pago_estado == "Pagada ✅":
                ingreso_hoy = abono_val if abono_val > 0 else val_sesion
                pagada_count = 1
            elif pago_estado == "Pagada (Excedente) ✅":
                ingreso_hoy = abono_val
                pagada_count = 1
            elif pago_estado in ["Saldada con Billetera ✅", "Pagada con Billetera ✅"]:
                ingreso_hoy = abono_val 
                pagada_count = 1
            elif pago_estado == "Abono Parcial ⏳":
                ingreso_hoy = abono_val
                deuda_hoy = max(0.0, val_sesion - abono_val)
                adeudada_count = 1
            elif pago_estado == "No pagada ❌":
                deuda_hoy = val_sesion
                adeudada_count = 1
                
            resultado["total_sesiones"] += 1
            resultado["pagadas"] += pagada_count
            resultado["adeudadas"] += adeudada_count
            resultado["ingresos"] += ingreso_hoy
            resultado["por_cobrar"] += deuda_hoy
            
            if boleta_estado == "Sí 🧾":
                resultado["ingresos_boleta"] += val_sesion
            
            if es_pauta:
                resultado["ingresos_pautas"] += ingreso_hoy
                resultado["deuda_pautas"] += deuda_hoy
            else:
                resultado["ingresos_sesiones"] += ingreso_hoy
                resultado["deuda_sesiones"] += deuda_hoy

        pacientes_totales = df_mes['Paciente_norm'].unique()
        pacientes_deuda = df_mes[df_mes['Pago'].isin(["No pagada ❌", "Abono Parcial ⏳"])]['Paciente_norm'].unique()
        resultado["pacientes_totales"] = len(pacientes_totales)
        resultado["pacientes_con_deuda"] = len(pacientes_deuda)
        return resultado

    def calcular_sesion_historica(nombre_paciente, fecha_actual, hora_actual):
        if nombre_paciente == "": return ""
        nombre_norm = str(nombre_paciente).strip().upper()
        df_completo = cargar_tabla("Clinica")
        if df_completo.empty or 'Paciente' not in df_completo.columns: return "1"
        df_hist = df_completo[(df_completo['Paciente'].str.strip().str.upper() == nombre_norm) & (~df_completo['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️", "Pauta Online 💻"]))].copy()
        if df_hist.empty: return "1"
        df_hist['FechaHora'] = pd.to_datetime(df_hist['Fecha'] + ' ' + df_hist['Hora'])
        fecha_hora_actual = pd.to_datetime(f"{fecha_actual} {hora_actual}")
        contador = len(df_hist[df_hist['FechaHora'] <= fecha_hora_actual])
        return str(contador if contador > 0 else 1)

    # --- EL CEREBRO DE LA BILLETERA (BARRIDO AUTOMÁTICO GOTA A GOTA) ---
    def ejecutar_barrido_billeteras():
        df_fichas = cargar_tabla("Fichas")
        df_clinica = cargar_tabla("Clinica")
        if df_fichas.empty or df_clinica.empty or 'Billetera' not in df_fichas.columns: return False
        
        mapa_val = obtener_valor_por_paciente()
        mapa_pau = obtener_valor_pauta_por_paciente()
        hubo_cambios = False
        
        df_fichas['Billetera'] = pd.to_numeric(df_fichas['Billetera'], errors='coerce').fillna(0.0)
        
        df_clinica['Fecha_Obj'] = pd.to_datetime(df_clinica['Fecha'], errors='coerce').dt.date
        hoy = date.today()
        
        for idx_f, row_f in df_fichas.iterrows():
            billetera = float(row_f['Billetera'])
            if billetera > 0:
                paciente = str(row_f['Paciente']).strip().upper()
                
                mask_deudas = (df_clinica['Paciente'].astype(str).str.strip().str.upper() == paciente) & \
                              (df_clinica['Pago'].isin(["No pagada ❌", "Abono Parcial ⏳", "-", "Descontar Billetera 💳"])) & \
                              (df_clinica['Fecha_Obj'] <= hoy)
                
                if mask_deudas.any():
                    idx_deudas = df_clinica[mask_deudas].sort_values(by=['Fecha', 'Hora']).index
                    for idxd in idx_deudas:
                        if billetera <= 0: break
                        motivo = str(df_clinica.at[idxd, 'Detalle / Motivo']).strip()
                        if motivo in ["Personal / Trámite 🛑", "Gimnasio 🏋️"]: continue
                        
                        val_total = mapa_pau.get(paciente, 0.0) if motivo == "Pauta Online 💻" else mapa_val.get(paciente, 0.0)
                        if val_total <= 0: continue 
                        
                        abono_previo = parse_dinero(df_clinica.at[idxd, 'Abono ($)'])
                        deuda_actual = val_total - abono_previo
                        
                        if deuda_actual > 0:
                            if billetera >= deuda_actual:
                                billetera -= deuda_actual
                                df_clinica.at[idxd, 'Pago'] = "Saldada con Billetera ✅"
                                hubo_cambios = True
                            else:
                                nuevo_abono = abono_previo + billetera
                                df_clinica.at[idxd, 'Abono ($)'] = str(int(nuevo_abono))
                                df_clinica.at[idxd, 'Pago'] = "Abono Parcial ⏳"
                                billetera = 0
                                hubo_cambios = True
                    
                    df_fichas.at[idx_f, 'Billetera'] = billetera
                    
        if hubo_cambios:
            if 'Fecha_Obj' in df_clinica.columns:
                df_clinica = df_clinica.drop(columns=['Fecha_Obj'])
            guardar_tabla("Clinica", df_clinica)
            guardar_tabla("Fichas", df_fichas)
            return True
        return False

    # --- CARGA DE DATOS ---
    df_clinica = cargar_datos_clinica(fecha_str)
    df_personal = cargar_datos_personal(fecha_str)

    # --- EL PUNTO ROJO EN LA TABLA ---
    if es_hoy:
        try:
            ahora_chile = pd.Timestamp.now('America/Santiago')
            hora_actual = ahora_chile.time()
            for idx, h_str in enumerate(horas_30_min):
                h_obj = datetime.strptime(h_str, "%H:%M").time()
                h_next = datetime.strptime(horas_30_min[idx+1], "%H:%M").time() if idx < len(horas_30_min)-1 else datetime.strptime("20:30", "%H:%M").time()
                if h_obj <= hora_actual < h_next:
                    if idx < len(df_clinica): df_clinica.at[idx, 'Hora'] = f"🔴 {h_str}"
                    if idx < len(df_personal): df_personal.at[idx, 'Hora'] = f"🔴 {h_str}"
                    break
        except: pass

    df_clinica['Paciente'] = df_clinica['Paciente'].fillna("") 
    df_clinica['Dirección'] = df_clinica['Dirección'].fillna("").astype(str)
    df_clinica['Minutos de Viaje'] = pd.to_numeric(df_clinica['Minutos de Viaje'], errors='coerce').fillna(0).astype(int)
    df_clinica['Hora de Salida'] = df_clinica['Hora de Salida'].fillna("").astype(str)
    df_clinica['Ruta Maps'] = df_clinica['Ruta Maps'].fillna("").astype(str)
    if 'Alarma' not in df_clinica.columns: df_clinica['Alarma'] = ""
    df_clinica['Alarma'] = df_clinica['Alarma'].fillna("").astype(str)
    df_clinica['N° Sesión'] = df_clinica['N° Sesión'].fillna("").astype(str)
    df_clinica['Pago'] = df_clinica['Pago'].fillna("-").astype(str)
    if 'Abono ($)' not in df_clinica.columns: df_clinica['Abono ($)'] = ""
    df_clinica['Abono ($)'] = df_clinica['Abono ($)'].fillna("").astype(str)
    if 'Boleta' not in df_clinica.columns: df_clinica['Boleta'] = "-"
    df_clinica['Boleta'] = df_clinica['Boleta'].fillna("-").astype(str)
    if 'Recordatorio' not in df_clinica.columns: df_clinica['Recordatorio'] = ""
    df_clinica['Recordatorio'] = df_clinica['Recordatorio'].fillna("").astype(str)

    df_personal['Actividad'] = df_personal['Actividad'].fillna("").astype(str)
    df_personal['Categoría'] = df_personal['Categoría'].fillna("-").astype(str)
    df_personal['Notas'] = df_personal['Notas'].fillna("").astype(str)

    # MAPEO SEGURO POR HORA
    mapa_pacientes_clinica = {}
    for _, row_c in df_clinica.iterrows():
        h_limp = str(row_c['Hora']).replace("🔴 ", "").replace("🔴", "").strip()
        p_val = str(row_c['Paciente']).strip()
        if p_val != "" and p_val.upper() != "ALMUERZO":
            mapa_pacientes_clinica[h_limp] = p_val

    for idx_p in df_personal.index:
        h_pers = str(df_personal.at[idx_p, 'Hora']).replace("🔴 ", "").replace("🔴", "").strip()
        act_personal = str(df_personal.at[idx_p, 'Actividad']).strip()
        if h_pers in mapa_pacientes_clinica:
            pac_clinica = mapa_pacientes_clinica[h_pers]
            if not act_personal.startswith("🩺 Atendiendo"):
                df_personal.at[idx_p, 'Actividad'] = f"🩺 Atendiendo: {pac_clinica}"
                df_personal.at[idx_p, 'Categoría'] = "Clínica"
        else:
            if act_personal.startswith("🩺 Atendiendo"):
                df_personal.at[idx_p, 'Actividad'] = ""
                df_personal.at[idx_p, 'Categoría'] = "-"

    mapa_personal = obtener_actividad_por_hora(df_personal) 
    mapa_telefonos = obtener_telefono_por_paciente()
    mapa_direcciones = obtener_direccion_por_paciente()

    for index in df_clinica.index:
        paciente = str(df_clinica.at[index, 'Paciente']).strip()
        direccion = str(df_clinica.at[index, 'Dirección']).strip()
        hora_str = str(df_clinica.at[index, 'Hora']).replace("🔴 ", "").replace("🔴", "").strip()
        minutos = int(df_clinica.at[index, 'Minutos de Viaje'])
        pago_actual = str(df_clinica.at[index, 'Pago']).strip()
        sesion_actual = str(df_clinica.at[index, 'N° Sesión']).strip()
        detalle_actual = str(df_clinica.at[index, 'Detalle / Motivo']).strip()
        actividad_personal = mapa_personal.get(hora_str, "") 
        es_tramite = (detalle_actual == "Personal / Trámite 🛑")
        es_gimnasio = (detalle_actual == "Gimnasio 🏋️")
        es_cita_clinica = (detalle_actual in ["Rehabilitación", "Entrenamiento", "Preventivo", "Pauta Online 💻"])
        es_almuerzo = (paciente.upper() == "ALMUERZO")
        hay_paciente = (paciente != "" and not es_almuerzo)
        
        if hay_paciente and direccion == "":
            dir_guardada = mapa_direcciones.get(paciente.upper(), "")
            if dir_guardada != "":
                direccion = dir_guardada
                df_clinica.at[index, 'Dirección'] = direccion

        if hay_paciente or es_tramite or es_gimnasio or es_cita_clinica:
            if direccion != "" and direccion != "-":
                query_maps = urllib.parse.quote(direccion + ", Chile")
                df_clinica.at[index, 'Ruta Maps'] = f"https://www.google.com/maps/search/?api=1&query={query_maps}"
            else: df_clinica.at[index, 'Ruta Maps'] = ""
            
            if minutos > 0:
                try:
                    tiempo_agendado = datetime.strptime(hora_str, "%H:%M")
                    tiempo_salida = tiempo_agendado - timedelta(minutes=(minutos + 5))
                    df_clinica.at[index, 'Hora de Salida'] = tiempo_salida.strftime("%H:%M")
                    formato_fecha = fecha_str.replace("-", "")
                    h_ini = tiempo_salida.strftime("%H%M%S")
                    h_fin = tiempo_agendado.strftime("%H%M%S")
                    txt_ev = urllib.parse.quote(f"🚗 VIAJE: {paciente if hay_paciente else detalle_actual}")
                    dest = urllib.parse.quote(direccion if direccion != "" else "Destino de atención")
                    df_clinica.at[index, 'Alarma'] = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={txt_ev}&dates={formato_fecha}T{h_ini}/{formato_fecha}T{h_fin}&details=Hora+de+salir+hacia:+{dest}"
                except:
                    df_clinica.at[index, 'Hora de Salida'] = ""
                    df_clinica.at[index, 'Alarma'] = ""
            else:
                df_clinica.at[index, 'Hora de Salida'] = ""
                df_clinica.at[index, 'Alarma'] = ""

            if es_tramite or es_gimnasio:
                df_clinica.at[index, 'Pago'] = "-"
                df_clinica.at[index, 'Boleta'] = "-"
                df_clinica.at[index, 'N° Sesión'] = "-"
            else:
                if pago_actual == "-" or pago_actual == "": df_clinica.at[index, 'Pago'] = "No pagada ❌"
                es_numero_auto = False
                if sesion_actual == "" or sesion_actual == "-": es_numero_auto = True
                else:
                    try: float(sesion_actual); es_numero_auto = True
                    except ValueError: es_numero_auto = False
                
                if es_numero_auto: 
                    if detalle_actual == "Pauta Online 💻":
                        df_clinica.at[index, 'N° Sesión'] = "Pauta"
                    else:
                        df_clinica.at[index, 'N° Sesión'] = calcular_sesion_historica(paciente, fecha_str, hora_str)
                        
            if hay_paciente and detalle_actual != "Pauta Online 💻":
                telefono_paciente = mapa_telefonos.get(paciente.strip().upper(), "")
                df_clinica.at[index, 'Recordatorio'] = construir_link_whatsapp(telefono_paciente, fecha_visual, hora_str)
            else: df_clinica.at[index, 'Recordatorio'] = ""
        else:
            df_clinica.at[index, 'Ruta Maps'] = ""; df_clinica.at[index, 'Hora de Salida'] = ""; df_clinica.at[index, 'Alarma'] = ""
            df_clinica.at[index, 'N° Sesión'] = ""; df_clinica.at[index, 'Pago'] = "-"; df_clinica.at[index, 'Recordatorio'] = ""; df_clinica.at[index, 'Boleta'] = "-"

        if actividad_personal != "" and (hay_paciente or es_cita_clinica):
            if actividad_personal.startswith("🩺 Atendiendo"): df_clinica.at[index, 'Estado'] = "Agendado 🔒"
            else: df_clinica.at[index, 'Estado'] = "⚠️ TOPE HORARIO ⚠️"
        elif actividad_personal != "": df_clinica.at[index, 'Estado'] = f"Bloqueado ({actividad_personal}) 🛑"
        elif es_tramite: df_clinica.at[index, 'Estado'] = "Bloqueado 🛑"
        elif es_gimnasio: df_clinica.at[index, 'Estado'] = "Gimnasio 🏋️"
        elif detalle_actual == "Pauta Online 💻": df_clinica.at[index, 'Estado'] = "Entregada 📩"
        elif es_cita_clinica or hay_paciente: df_clinica.at[index, 'Estado'] = "Agendado 🔒"
        elif es_almuerzo: df_clinica.at[index, 'Estado'] = "-"
        else:
            if index > 0:
                paciente_ant = str(df_clinica.at[index - 1, 'Paciente']).strip()
                detalle_ant = str(df_clinica.at[index - 1, 'Detalle / Motivo']).strip()
                if (detalle_ant == "Personal / Trámite 🛑") or (detalle_ant == "Gimnasio 🏋️"):
                    df_clinica.at[index, 'Estado'] = f"Bloqueado ({paciente_ant if paciente_ant != '' else ('Trámite' if detalle_ant == 'Personal / Trámite 🛑' else 'Gimnasio')}) ⏳"
                    continue
                elif (detalle_ant in ["Rehabilitación", "Entrenamiento", "Preventivo", "Pauta Online 💻"]) or (paciente_ant != "" and paciente_ant.upper() != "ALMUERZO"):
                    df_clinica.at[index, 'Estado'] = f"En sesión ({paciente_ant if paciente_ant != '' else 'Paciente'}) ⏳"
                    continue
            df_clinica.at[index, 'Estado'] = "Libre 🟢"

    # --- PESTAÑAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["🩺 Calendario", "🕰️ Horario Personal", "📁 Fichas Clínicas", "📊 Dashboard"])

    with tab1:
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1: 
            st.header(f"📅 Agenda Clínica - {fecha_visual}")
            if es_hoy:
                try:
                    ahora_chile = pd.Timestamp.now('America/Santiago')
                    inicio_dia = ahora_chile.replace(hour=8, minute=0, second=0, microsecond=0)
                    fin_dia = ahora_chile.replace(hour=20, minute=30, second=0, microsecond=0)
                    if inicio_dia <= ahora_chile <= fin_dia:
                        total_minutos = (fin_dia - inicio_dia).total_seconds() / 60
                        minutos_transcurridos = (ahora_chile - inicio_dia).total_seconds() / 60
                        pct = max(0, min(100, (minutos_transcurridos / total_minutos) * 100))
                        hora_actual_str = ahora_chile.strftime('%H:%M')
                        hora_actual_time = ahora_chile.time()
                        
                        texto_proximo = ""
                        for i_h, h_str_b in enumerate(horas_30_min):
                            h_obj_b = datetime.strptime(h_str_b, "%H:%M").time()
                            if h_obj_b > hora_actual_time and i_h < len(df_clinica) and i_h < len(df_personal):
                                pac_b = str(df_clinica.at[i_h, 'Paciente']).strip()
                                mot_b = str(df_clinica.at[i_h, 'Detalle / Motivo']).strip()
                                act_b = str(df_personal.at[i_h, 'Actividad']).strip()
                                
                                evento_b = ""
                                if pac_b != "" and pac_b.upper() != "ALMUERZO":
                                    if mot_b == "Pauta Online 💻":
                                        evento_b = f"Pauta Online: {pac_b}"
                                    else:
                                        evento_b = f"Paciente: {pac_b}"
                                elif mot_b in ["Gimnasio 🏋️", "Personal / Trámite 🛑"]:
                                    evento_b = mot_b.replace(' 🏋️', '').replace(' 🛑', '')
                                elif pac_b.upper() == "ALMUERZO":
                                    evento_b = "Almuerzo"
                                elif act_b != "":
                                    evento_b = act_b.replace("🩺 Atendiendo: ", "Paciente: ")
                                    
                                if evento_b != "":
                                    hora_evento_dt = ahora_chile.replace(hour=h_obj_b.hour, minute=h_obj_b.minute, second=0, microsecond=0)
                                    mins_faltantes = int((hora_evento_dt - ahora_chile).total_seconds() / 60)
                                    texto_proximo = f"<div style='margin-top: 15px; padding-top: 12px; border-top: 1px dashed #bdc3c7;'><span style='color: #e67e22; font-size: 0.95rem; font-weight: bold;'>👉 Próximo a las {h_str_b}: {evento_b} (en {mins_faltantes} min)</span></div>"
                                    break
                                    
                        if texto_proximo == "":
                            texto_proximo = "<div style='margin-top: 15px; padding-top: 12px; border-top: 1px dashed #bdc3c7;'><span style='color: #18BC9C; font-size: 0.95rem; font-weight: bold;'>👉 No hay más eventos agendados. ¡Turno terminado! 🎉</span></div>"

                        linea_html = f"""
                        <div style="margin: 25px 0 35px 0; padding: 15px 20px; background: white; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); border: 1px solid #f0f2f6;">
                            <p style="margin-top: 0; margin-bottom: 20px; color: #2C3E50; font-weight: bold; font-size: 0.95rem;">
                                ⏳ Tracking de Jornada (Faltan {int(total_minutos - minutos_transcurridos)} min para terminar el día)
                            </p>
                            <div style="position: relative; width: 100%; height: 6px; background-color: #E0E6ED; border-radius: 3px;">
                                <div style="position: absolute; left: 0; top: 0; height: 100%; width: {pct}%; background-color: #E74C3C; border-radius: 3px;"></div>
                                <div style="position: absolute; left: {pct}%; top: -7px; transform: translateX(-50%); width: 20px; height: 20px; background-color: #E74C3C; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"></div>
                                <div style="position: absolute; left: {pct}%; top: -35px; transform: translateX(-50%); background-color: #E74C3C; color: white; padding: 4px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: bold; z-index: 10;">{hora_actual_str}</div>
                            </div>
                            <div style="display: flex; justify-content: space-between; color: #95a5a6; font-size: 0.8rem; font-weight: 600; margin-top: 15px;">
                                <span>08:00</span>
                                <span>14:00</span>
                                <span>20:30</span>
                            </div>
                            {texto_proximo}
                        </div>
                        """
                        st.markdown(linea_html, unsafe_allow_html=True)
                except: pass
                
        with col_t2:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            btn_guardar_clinica = st.button("💾 Guardar Cambios", use_container_width=True, type="primary", key="btn_save_clinica")
        
        with st.expander("⚡ Agendar Existente / Paquetes / Reagendar"):
            tab_ex, tab_ag, tab_re = st.tabs(["➕ Un Paciente Existente", "🔄 Múltiples Sesiones", "✂️ Reagendar Cita"])
            
            with tab_ex:
                lista_pacs = obtener_lista_pacientes()
                if not lista_pacs:
                    st.info("Primero agrega un paciente manualmente en la tabla inferior o en Fichas Clínicas.")
                else:
                    col_e1, col_e2, col_e3 = st.columns(3)
                    with col_e1:
                        pac_ex = st.selectbox("1. Paciente Existente:", ["-- Selecciona --"] + lista_pacs)
                        mot_ex = st.selectbox("Motivo de sesión:", ["Rehabilitación", "Entrenamiento", "Preventivo", "Pauta Online 💻"], key="mot_ex")
                    with col_e2:
                        hora_ex = st.selectbox(f"2. Hora (para este día):", horas_30_min, key="hora_ex")
                    with col_e3:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        btn_ex = st.button("🚀 Agendar en esta hora", use_container_width=True)
                    if btn_ex:
                        if pac_ex == "-- Selecciona --": st.error("Por favor selecciona un paciente.")
                        else:
                            idx_ex = df_clinica.index[df_clinica['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_ex].tolist()[0]
                            if str(df_clinica.at[idx_ex, 'Paciente']).strip() != "": st.error("⚠️ Esta hora ya está ocupada.")
                            else:
                                with st.spinner("Agendando..."):
                                    df_clinica.at[idx_ex, 'Paciente'] = pac_ex
                                    df_clinica.at[idx_ex, 'Detalle / Motivo'] = mot_ex
                                    df_clinica.at[idx_ex, 'Dirección'] = mapa_direcciones.get(pac_ex.upper(), "")
                                    df_clinica.at[idx_ex, 'Minutos de Viaje'] = 0
                                    df_clinica.at[idx_ex, 'Pago'] = "No pagada ❌"
                                    df_clinica.at[idx_ex, 'Boleta'] = "-"
                                    df_clinica.at[idx_ex, 'N° Sesión'] = ""
                                    guardar_dia("Clinica", fecha_str, df_clinica)
                                    if ejecutar_barrido_billeteras():
                                        st.toast("⛽ ¡El Tanque cubrió esta sesión automáticamente!")
                                    st.success(f"✅ ¡{pac_ex} agendado a las {hora_ex}!")
                                    time.sleep(1)
                                    st.rerun()

            with tab_ag:
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    m_paciente = st.text_input("Paciente:")
                    m_motivo = st.selectbox("Motivo:", ["Rehabilitación", "Entrenamiento", "Preventivo", "Pauta Online 💻"])
                    m_sesiones = st.number_input("N° de sesiones:", min_value=1, value=10, step=1)
                with col_m2:
                    m_fecha_inicio = st.date_input("Inicio:")
                    m_hora = st.selectbox("Hora:", horas_30_min)
                    dias_map = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4, "Sábado": 5, "Domingo": 6}
                    m_dias = st.multiselect("Días:", list(dias_map.keys()), default=["Lunes", "Miércoles"])
                with col_m3:
                    m_direccion = st.text_input("Dirección (opc.):")
                    m_viaje = st.number_input("Viaje (min):", min_value=0, value=0, step=1)
                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_agendar = st.button("🚀 Programar", use_container_width=True)

                if btn_agendar:
                    if m_paciente.strip() == "": st.error("Ingresa el paciente.")
                    elif not m_dias: st.error("Selecciona días.")
                    else:
                        sesiones_logradas, dias_buscados = 0, 0
                        fecha_iter, dias_obj = m_fecha_inicio, [dias_map[d] for d in m_dias]
                        fechas_exitosas, fechas_ocupadas = [], []
                        with st.spinner('Agendando...'):
                            while sesiones_logradas < m_sesiones and dias_buscados < 365:
                                if fecha_iter.weekday() in dias_obj:
                                    f_str = fecha_iter.strftime("%Y-%m-%d")
                                    df_dia_futuro = cargar_datos_clinica(f_str)
                                    df_pers_futuro = cargar_datos_personal(f_str)
                                    mapa_personal_futuro = obtener_actividad_por_hora(df_pers_futuro) 
                                    idx_hora = df_dia_futuro.index[df_dia_futuro['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == m_hora].tolist()
                                    if idx_hora:
                                        idx = idx_hora[0]
                                        p_act = str(df_dia_futuro.at[idx, 'Paciente']).strip()
                                        d_act = str(df_dia_futuro.at[idx, 'Detalle / Motivo']).strip()
                                        a_act = mapa_personal_futuro.get(m_hora, "")
                                        ocupado = True if p_act != "" or d_act in ["Personal / Trámite 🛑", "Gimnasio 🏋️"] or (a_act != "" and not a_act.startswith("🩺")) else False
                                        if not ocupado:
                                            df_dia_futuro.at[idx, 'Paciente'] = m_paciente
                                            df_dia_futuro.at[idx, 'Detalle / Motivo'] = m_motivo
                                            dir_final = m_direccion
                                            if dir_final == "": dir_final = mapa_direcciones.get(m_paciente.strip().upper(), "")
                                            df_dia_futuro.at[idx, 'Dirección'] = dir_final
                                            df_dia_futuro.at[idx, 'Minutos de Viaje'] = m_viaje
                                            df_dia_futuro.at[idx, 'Pago'] = "No pagada ❌"
                                            df_dia_futuro.at[idx, 'Boleta'] = "-"
                                            df_dia_futuro.at[idx, 'N° Sesión'] = "" 
                                            exito_agendar = guardar_dia("Clinica", f_str, df_dia_futuro)
                                            if exito_agendar:
                                                fechas_exitosas.append(fecha_iter.strftime("%d/%m/%Y"))
                                                sesiones_logradas += 1
                                                time.sleep(0.3)
                                        else: fechas_ocupadas.append(fecha_iter.strftime("%d/%m/%Y"))
                                fecha_iter += timedelta(days=1)
                                dias_buscados += 1
                                
                            if sesiones_logradas > 0 and m_direccion.strip() != "":
                                df_fichas_sync = cargar_tabla("Fichas")
                                if df_fichas_sync.empty or 'Paciente' not in df_fichas_sync.columns:
                                    df_fichas_sync = pd.DataFrame(columns=['Paciente', 'Teléfono', 'Edad', 'Diagnóstico', 'Notas Clínicas', 'Valor Sesión', 'Dirección', 'Valor Pauta', 'Billetera'])
                                if 'Dirección' not in df_fichas_sync.columns: df_fichas_sync['Dirección'] = ""
                                if 'Valor Pauta' not in df_fichas_sync.columns: df_fichas_sync['Valor Pauta'] = ""
                                if 'Billetera' not in df_fichas_sync.columns: df_fichas_sync['Billetera'] = 0.0
                                
                                mask_f = df_fichas_sync['Paciente'].astype(str).str.strip().str.upper() == m_paciente.strip().upper()
                                if mask_f.any():
                                    idx_f = df_fichas_sync[mask_f].index[0]
                                    if str(df_fichas_sync.at[idx_f, 'Dirección']).strip() != m_direccion.strip():
                                        df_fichas_sync.at[idx_f, 'Dirección'] = m_direccion.strip()
                                        guardar_tabla("Fichas", df_fichas_sync)
                                else:
                                    nueva_fila = pd.DataFrame({'Paciente': [m_paciente.strip().title()], 'Teléfono': [""], 'Edad': [""], 'Diagnóstico': [""], 'Notas Clínicas': [""], 'Valor Sesión': [""], 'Dirección': [m_direccion.strip()], 'Valor Pauta': [""], 'Billetera': [0.0]})
                                    df_fichas_sync = pd.concat([df_fichas_sync, nueva_fila], ignore_index=True)
                                    guardar_tabla("Fichas", df_fichas_sync)
                            
                            if ejecutar_barrido_billeteras():
                                st.toast("⛽ ¡El Tanque cubrió las sesiones agendadas automáticamente!")

                        if sesiones_logradas == m_sesiones: st.success("✅ ¡Agendado!")
                        else: st.warning(f"⚠️ Solo se agendaron {sesiones_logradas}.")
                        st.rerun()

            with tab_re:
                sesiones_activas = df_clinica[(df_clinica['Paciente'].str.strip() != "") & (df_clinica['Paciente'].str.upper() != "ALMUERZO")]
                opciones_citas = ["-- Selecciona --"] + [f"{str(r['Hora']).replace('🔴 ', '')} - {r['Paciente']}" for i, r in sesiones_activas.iterrows()]
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    cita_origen = st.selectbox("Cita de hoy:", opciones_citas)
                    accion_reagendar = st.radio("Acción:", ["Mover", "Duplicar"])
                with col_r2:
                    fecha_destino = st.date_input("Nueva fecha:", value=st.session_state.app_fecha_sel + timedelta(days=1))
                    hora_destino = st.selectbox("Nueva hora:", horas_30_min, key="hora_destino_reagendar")
                with col_r3:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    btn_reagendar = st.button("🚀 Ejecutar", use_container_width=True)
                if btn_reagendar and cita_origen != "-- Selecciona --":
                    hora_origen = cita_origen.split(" - ")[0].replace("🔴 ", "").replace("🔴", "").strip()
                    idx_origen_list = df_clinica.index[df_clinica['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_origen].tolist()
                    if idx_origen_list:
                        fila_origen = df_clinica.iloc[idx_origen_list[0]]
                        f_dest_str = fecha_destino.strftime("%Y-%m-%d")
                        df_clinica_dest = cargar_datos_clinica(f_dest_str)
                        idx_dest = df_clinica_dest.index[df_clinica_dest['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_destino].tolist()[0]
                        if str(df_clinica_dest.at[idx_dest, 'Paciente']).strip() != "":
                            st.error("⚠️ La hora de destino está ocupada.")
                        else:
                            with st.spinner("Procesando..."):
                                df_clinica_dest.at[idx_dest, 'Paciente'] = str(fila_origen['Paciente'])
                                df_clinica_dest.at[idx_dest, 'Detalle / Motivo'] = str(fila_origen['Detalle / Motivo'])
                                df_clinica_dest.at[idx_dest, 'Dirección'] = str(fila_origen['Dirección'])
                                df_clinica_dest.at[idx_dest, 'Minutos de Viaje'] = int(fila_origen['Minutos de Viaje'])
                                df_clinica_dest.at[idx_dest, 'Pago'] = "No pagada ❌"
                                df_clinica_dest.at[idx_dest, 'Boleta'] = "-"
                                df_clinica_dest.at[idx_dest, 'N° Sesión'] = "" 
                                exito_r = guardar_dia("Clinica", f_dest_str, df_clinica_dest)
                                if exito_r and accion_reagendar == "Mover":
                                    idx_origen = df_clinica.index[df_clinica['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_origen].tolist()[0]
                                    df_clinica.at[idx_origen, 'Paciente'] = ""
                                    df_clinica.at[idx_origen, 'Detalle / Motivo'] = "-"
                                    df_clinica.at[idx_origen, 'Dirección'] = ""
                                    df_clinica.at[idx_origen, 'Minutos de Viaje'] = 0
                                    df_clinica.at[idx_origen, 'Pago'] = "-"
                                    df_clinica.at[idx_origen, 'Boleta'] = "-"
                                    df_clinica.at[idx_origen, 'N° Sesión'] = ""
                                    guardar_dia("Clinica", fecha_str, df_clinica)
                                if ejecutar_barrido_billeteras():
                                    st.toast("⛽ ¡El Tanque cubrió la reagendación automáticamente!")
                                if exito_r:
                                    st.success("✅ ¡Listo!")
                                    time.sleep(1)
                                    st.rerun()

        with st.expander("🔍 Buscador de Pacientes"):
            lista_pacientes_buscador = obtener_lista_pacientes()
            if not lista_pacientes_buscador: st.info("No hay pacientes agendados.")
            else:
                paciente_buscar = st.selectbox("Selecciona un paciente:", ["-- Selecciona --"] + lista_pacientes_buscador, key="buscador_paciente_cal")
                if paciente_buscar != "-- Selecciona --":
                    df_full_clinica = cargar_tabla("Clinica")
                    if not df_full_clinica.empty and 'Paciente' in df_full_clinica.columns:
                        df_filtro = df_full_clinica[df_full_clinica['Paciente'].astype(str).str.strip().str.upper() == paciente_buscar.upper()]
                        if not df_filtro.empty:
                            df_resumen = df_filtro[['Fecha', 'Hora', 'Detalle / Motivo', 'Estado', 'Pago']].sort_values(by=['Fecha', 'Hora'])
                            st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                            
                            st.markdown("🎯 **Ir directamente al día para editar:**")
                            col_b1, col_b2 = st.columns([3, 1])
                            with col_b1:
                                opciones_sesiones = ["-- Elige una sesión --"] + [f"{r['Fecha']} a las {r['Hora']} ({r['Pago']})" for i, r in df_resumen.iterrows()]
                                sesion_a_editar = st.selectbox("Seleccionar sesión", opciones_sesiones, label_visibility="collapsed")
                            with col_b2:
                                if st.button("🚀 Viajar al Día", use_container_width=True):
                                    if sesion_a_editar != "-- Elige una sesión --":
                                        fecha_destino_str = sesion_a_editar.split(" a las ")[0]
                                        try:
                                            fecha_obj = datetime.strptime(fecha_destino_str, "%Y-%m-%d").date()
                                            st.session_state.app_fecha_sel = fecha_obj
                                            st.session_state.app_mes_cal = fecha_obj.replace(day=1)
                                            st.session_state.app_vista = "dia"
                                            st.rerun()
                                        except: pass
                                    else: st.error("Selecciona una cita válida de la lista.")
                        else: st.warning("No se encontraron sesiones.")

        with st.expander("📲 Enviar a Google Calendar"):
            correo_cal = st.text_input("Tu correo de Google Calendar (al que compartiste el acceso):", value="")
            if st.button("🚀 Sincronizar este día", type="primary", use_container_width=True):
                if correo_cal.strip() == "":
                    st.error("Debes ingresar tu correo.")
                else:
                    try:
                        from googleapiclient.discovery import build
                        with st.spinner("Creando eventos en tu calendario..."):
                            service = build('calendar', 'v3', credentials=credenciales_gcp)
                            eventos_creados = 0
                            
                            for idx, row in df_clinica.iterrows():
                                pac = str(row['Paciente']).strip()
                                motivo = str(row['Detalle / Motivo']).strip()
                                
                                if pac != "" and pac.upper() != "ALMUERZO" and motivo != "Pauta Online 💻":
                                    hora = str(row['Hora']).replace("🔴", "").strip()
                                    direccion = str(row['Dirección']).strip()
                                    min_viaje = int(row['Minutos de Viaje'])
                                    
                                    h_ini = datetime.strptime(f"{fecha_str} {hora}", "%Y-%m-%d %H:%M")
                                    h_fin = h_ini + timedelta(minutes=45)
                                    minutos_aviso = 30 + min_viaje
                                    
                                    evento = {
                                        'summary': f'🩺 Kine: {pac}',
                                        'location': direccion,
                                        'description': f'Motivo: {motivo}',
                                        'start': {'dateTime': h_ini.strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': 'America/Santiago'},
                                        'end': {'dateTime': h_fin.strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': 'America/Santiago'},
                                        'reminders': {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': minutos_aviso}]},
                                    }
                                    service.events().insert(calendarId=correo_cal, body=evento).execute()
                                    eventos_creados += 1
                            if eventos_creados > 0:
                                st.success(f"✅ ¡Éxito! Se crearon {eventos_creados} eventos en tu Google Calendar para hoy.")
                            else:
                                st.info("No hay pacientes agendados para sincronizar hoy.")
                    except ImportError:
                        st.error("🚨 Falta instalar la librería. Ve a tu GitHub y agrega `google-api-python-client` en tu archivo `requirements.txt`.")
                    except Exception as e:
                        st.error(f"🚨 Error de permisos con Google: {e}")

        with st.expander("📍 Viajes y Tiempos"):
            ubicacion_gps = streamlit_geolocation()
            direccion_base = st.text_input("O escribe tu base:", value="Gomez Carreño, Viña del Mar")
            if st.button("⚡ Calcular Tiempos Automáticos de Hoy"):
                with st.spinner("Calculando..."):
                    origen_final = direccion_base
                    fallos = 0
                    if ubicacion_gps and ubicacion_gps.get('latitude') is not None: origen_final = (ubicacion_gps['latitude'], ubicacion_gps['longitude'])
                    for idx in df_clinica.index:
                        dir_paciente, hora_paciente = str(df_clinica.at[idx, 'Dirección']).strip(), str(df_clinica.at[idx, 'Hora']).replace("🔴 ", "").replace("🔴", "").strip()
                        if dir_paciente != "":
                            minutos_gps = calcular_tiempo_gps(origen_final, dir_paciente)
                            if minutos_gps > 0: df_clinica.at[idx, 'Minutos de Viaje'] = minutos_gps
                            else: fallos += 1
                    exito = guardar_dia("Clinica", fecha_str, df_clinica)
                    if exito: 
                        if fallos > 0: st.warning(f"Se calculó, pero el mapa falló en {fallos} dirección(es). Pon los minutos manualmente.")
                        else: st.success("¡Calculado!")
                    st.rerun()

        st.caption("💡 Tip: Si el pago incluyó Boleta SII, márcalo en la columna 'Boleta SII' para que el Dashboard separe la retención de tus ganancias líquidas.")
        df_clinica_editado = st.data_editor(
            df_clinica, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"editor_clinica_{fecha_str}",
            column_order=("Hora", "Paciente", "Detalle / Motivo", "Dirección", "Minutos de Viaje", "Hora de Salida", "Ruta Maps", "Recordatorio", "Estado", "N° Sesión", "Pago", "Abono ($)", "Boleta"),
            column_config={
                "Hora": st.column_config.TextColumn("Hora", disabled=True),
                "Detalle / Motivo": st.column_config.SelectboxColumn("Motivo", options=["Rehabilitación", "Entrenamiento", "Preventivo", "Pauta Online 💻", "Personal / Trámite 🛑", "Gimnasio 🏋️", "-"]),
                "Dirección": st.column_config.TextColumn("Dirección"),
                "Minutos de Viaje": st.column_config.NumberColumn("Min. Viaje", min_value=0, step=1),
                "Hora de Salida": st.column_config.TextColumn("Salida", disabled=True),
                "Ruta Maps": st.column_config.LinkColumn("🗺️ Mapa", disabled=True, display_text="Ver Mapa"),
                "Recordatorio": st.column_config.LinkColumn("📲 WhatsApp", disabled=True, display_text="Enviar"),
                "Estado": st.column_config.TextColumn("Estado", disabled=True),
                "N° Sesión": st.column_config.TextColumn("Sesión", help="Calculado auto."),
                "Pago": st.column_config.SelectboxColumn("Pago", options=["No pagada ❌", "Pagada ✅", "Abono Parcial ⏳", "Descontar Billetera 💳", "Saldada con Billetera ✅", "Pagada con Billetera ✅", "Pagada (Excedente) ✅", "-"]),
                "Abono ($)": st.column_config.TextColumn("Abono ($)", help="Escribe en miles (ej: 30)"),
                "Boleta": st.column_config.SelectboxColumn("Boleta SII", options=["Sí 🧾", "No 🚫", "-"], help="¿Emitiste Boleta de Honorarios para este ingreso?")
            }
        )
        if btn_guardar_clinica:
            df_fichas_sync = cargar_tabla("Fichas")
            if df_fichas_sync.empty or 'Paciente' not in df_fichas_sync.columns:
                df_fichas_sync = pd.DataFrame(columns=['Paciente', 'Teléfono', 'Edad', 'Diagnóstico', 'Notas Clínicas', 'Valor Sesión', 'Dirección', 'Valor Pauta', 'Billetera'])
            if 'Dirección' not in df_fichas_sync.columns: df_fichas_sync['Dirección'] = ""
            if 'Valor Pauta' not in df_fichas_sync.columns: df_fichas_sync['Valor Pauta'] = ""
            if 'Billetera' not in df_fichas_sync.columns: df_fichas_sync['Billetera'] = 0.0
            
            df_fichas_sync['Billetera'] = pd.to_numeric(df_fichas_sync['Billetera'], errors='coerce').fillna(0.0)
            
            cambios_fichas = False
            mapa_val = obtener_valor_por_paciente()
            mapa_pau = obtener_valor_pauta_por_paciente()
            
            # Lógica para la edición del día
            for idx, r in df_clinica_editado.iterrows():
                pac = str(r['Paciente']).strip()
                dir_cal = str(r['Dirección']).strip()
                if pac != "" and pac.upper() != "ALMUERZO":
                    
                    mask_f = df_fichas_sync['Paciente'].astype(str).str.strip().str.upper() == pac.upper()
                    if mask_f.any():
                        idx_f = df_fichas_sync[mask_f].index[0]
                        if dir_cal != "" and dir_cal != "-" and str(df_fichas_sync.at[idx_f, 'Dirección']).strip() != dir_cal:
                            df_fichas_sync.at[idx_f, 'Dirección'] = dir_cal
                            cambios_fichas = True
                    elif dir_cal != "" and dir_cal != "-":
                        nueva_fila = pd.DataFrame({'Paciente': [pac.title()], 'Teléfono': [""], 'Edad': [""], 'Diagnóstico': [""], 'Notas Clínicas': [""], 'Valor Sesión': [""], 'Dirección': [dir_cal], 'Valor Pauta': [""], 'Billetera': [0.0]})
                        df_fichas_sync = pd.concat([df_fichas_sync, nueva_fila], ignore_index=True)
                        cambios_fichas = True
                        idx_f = df_fichas_sync.index[-1]
                    else:
                        continue 
                        
                    pago_est = str(r['Pago']).strip()
                    abono_val = parse_dinero(r['Abono ($)'])
                    
                    # Limpiamos visualmente la celda para que "30" se convierta en "30000" a la vista
                    df_clinica_editado.at[idx, 'Abono ($)'] = str(int(abono_val)) if abono_val > 0 else ""

                    motivo = str(r['Detalle / Motivo']).strip()
                    val_ses = mapa_pau.get(pac.upper(), 0.0) if motivo == "Pauta Online 💻" else mapa_val.get(pac.upper(), 0.0)
                    billetera_act = float(df_fichas_sync.at[idx_f, 'Billetera'])
                    
                    # Evaluamos los ingresos manuales del día solo si agrega plata al tanque
                    if abono_val > val_ses and val_ses > 0 and pago_est not in ["Pagada (Excedente) ✅"]:
                        excedente = abono_val - val_ses
                        df_fichas_sync.at[idx_f, 'Billetera'] = billetera_act + excedente
                        df_clinica_editado.at[idx, 'Pago'] = "Pagada (Excedente) ✅"
                        cambios_fichas = True
                        st.toast(f"⛽ Se guardaron ${excedente:,.0f} en el tanque de {pac}")
                    elif abono_val == val_ses and val_ses > 0 and pago_est not in ["Pagada ✅", "Pagada (Excedente) ✅", "Saldada con Billetera ✅", "Pagada con Billetera ✅"]:
                        df_clinica_editado.at[idx, 'Pago'] = "Pagada ✅"
                    elif 0 < abono_val < val_ses and pago_est not in ["Abono Parcial ⏳", "Saldada con Billetera ✅", "Pagada con Billetera ✅"]:
                        df_clinica_editado.at[idx, 'Pago'] = "Abono Parcial ⏳"
            
            if cambios_fichas:
                guardar_tabla("Fichas", df_fichas_sync)

            exito1 = guardar_dia("Clinica", fecha_str, df_clinica_editado)
            exito2 = guardar_dia("Personal", fecha_str, df_personal)
            
            if exito1:
                # El Tanque Mágico se activa automáticamente GOTA A GOTA (no toca el futuro)
                if ejecutar_barrido_billeteras():
                    st.toast("⛽ 👋 El Tanque Mágico descontó sesiones impagas automáticamente!")
                        
            if exito1 and exito2:
                st.success("¡Agenda guardada y Tanque de Bencina sincronizado!")
                time.sleep(1.5)
                st.rerun()

    with tab2:
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1: st.header(f"🕰️ Horario Personal - {fecha_visual}")
        with col_p2:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            btn_guardar_personal = st.button("💾 Guardar Personal", use_container_width=True, type="primary", key="btn_save_personal")
            
        with st.expander("⏳ Bloqueos de Agenda (Por Horas o Día Completo)"):
            tab_bloq_hora, tab_bloq_dia = st.tabs(["⏱️ Por Horas", "🚫 Día Completo"])
            
            with tab_bloq_hora:
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    hora_inicio_b = st.selectbox("Desde las:", horas_30_min, key="h_ini_bloqueo")
                    duracion_b = st.selectbox("Duración:", ["30 minutos", "60 minutos (1 hora)", "90 minutos (1.5 horas)", "120 minutos (2 horas)", "180 minutos (3 horas)", "240 minutos (4 horas)"])
                with col_b2:
                    act_b = st.text_input("Actividad:")
                    cat_b = st.selectbox("Categoría:", ["Tesis Magíster", "Proyecto Sustancia X", "Mascota", "Salud", "Ocio", "Trámites", "Clínica", "General", "-"], key="cat_b")
                with col_b3:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    btn_aplicar_bloqueo = st.button("🚀 Aplicar Bloqueo", use_container_width=True)
                    
                if btn_aplicar_bloqueo:
                    if act_b.strip() == "": st.error("Escribe el nombre de la actividad.")
                    else:
                        slots_necesarios = int(duracion_b.split(" ")[0]) // 30
                        idx_inicio = df_personal.index[df_personal['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_inicio_b].tolist()[0]
                        idx_fin = min(idx_inicio + slots_necesarios, len(df_personal))
                        
                        with st.spinner("Bloqueando..."):
                            for i in range(idx_inicio, idx_fin):
                                if not str(df_personal.at[i, 'Actividad']).startswith("🩺 Atendiendo"):
                                    df_personal.at[i, 'Actividad'] = act_b
                                    df_personal.at[i, 'Categoría'] = cat_b
                            guardar_dia("Personal", fecha_str, df_personal)
                            st.success(f"✅ ¡Bloqueo de {duracion_b} aplicado!")
                            time.sleep(1)
                            st.rerun()

            with tab_bloq_dia:
                motivo_dia = st.text_input("Motivo del bloqueo (ej: Feriado, Vacaciones, Trámites, Enfermedad):", key="motivo_dia_completo")
                col_bd1, col_bd2 = st.columns(2)
                with col_bd1:
                    btn_bloquear_dia = st.button("🚫 Bloquear Día Completo", use_container_width=True, type="primary")
                with col_bd2:
                    btn_desbloquear_dia = st.button("🔓 Liberar Día Completo", use_container_width=True)
                    
                if btn_bloquear_dia:
                    if motivo_dia.strip() == "": st.error("Escribe un motivo primero.")
                    else:
                        with st.spinner("Bloqueando todo el día..."):
                            for i in range(len(df_personal)):
                                if not str(df_personal.at[i, 'Actividad']).startswith("🩺 Atendiendo"):
                                    df_personal.at[i, 'Actividad'] = motivo_dia
                                    df_personal.at[i, 'Categoría'] = "General"
                            guardar_dia("Personal", fecha_str, df_personal)
                            st.success("✅ ¡Día bloqueado completo!")
                            time.sleep(1)
                            st.rerun()
                
                if btn_desbloquear_dia:
                    with st.spinner("Liberando el día..."):
                        for i in range(len(df_personal)):
                            if not

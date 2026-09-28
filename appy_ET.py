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
st.set_page_config(page_title="Agenda Clases de Inglés", page_icon="🇬🇧", layout="wide")

# --- ESTILOS PERSONALIZADOS AVANZADOS ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .titulo-principal { color: #2C3E50; text-align: center; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 800; font-size: 2.5rem; margin-bottom: -10px; }
    .subtitulo { color: #E74C3C; text-align: center; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 600; font-size: 1.2rem; margin-bottom: 2rem; }
    
    div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button {
        width: 100% !important; padding: 12px 0px !important; border-radius: 8px !important;
        font-size: 1rem !important; font-weight: 700 !important; box-shadow: 0px 1px 3px rgba(0,0,0,0.1) !important;
        border: 1px solid #E0E6ED !important; min-height: 45px !important;
    }

    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) {
            display: grid !important; grid-template-columns: repeat(7, 1fr) !important; gap: 4px !important; width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) > div[data-testid="column"] {
            width: 100% !important; min-width: 0 !important; padding: 0 !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button {
            padding: 8px 0px !important; font-size: 0.85rem !important; border-radius: 6px !important; min-height: 40px !important;
        }
        .dia-semana { font-size: 0.75rem !important; }
        .titulo-principal { font-size: 1.8rem !important; }
        .subtitulo { font-size: 1rem !important; }
    }
    button[data-baseweb="tab"] { font-size: 1rem !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="titulo-principal">Centro de Mando Pedagógico</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitulo">Clases de Inglés — Organización y Finanzas</p>', unsafe_allow_html=True)

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
    
    # robot-agenda-kine-cgm@agenda-kine-cgm.iam.gserviceaccount.com:
    doc_ingles = cliente.open_by_url("https://docs.google.com/spreadsheets/d/TU_NUEVO_ENLACE_AQUI/edit")
    
    return doc_ingles, creds

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
        if str(val).strip() == "": return 0.0
        return float(str(val).replace('$', '').replace('.', '').replace(',', '').strip())
    except:
        return 0.0

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
    with col_mes1: st.button("⬅️ Anterior", on_click=cambiar_mes, args=(-1,), use_container_width=True)
    with col_mes2:
        meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        año_act = st.session_state.app_mes_cal.year
        mes_act = st.session_state.app_mes_cal.month
        st.markdown(f"<h3 style='text-align: center; color: #2C3E50; margin-top: 0;'>{meses_es[mes_act-1]} {año_act}</h3>", unsafe_allow_html=True)
    with col_mes3: st.button("Siguiente ➡️", on_click=cambiar_mes, args=(1,), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    cols_dias = st.columns(7)
    for i, d in enumerate(dias_semana):
        cols_dias[i].markdown(f"<div class='dia-semana' style='text-align:center; font-weight:700; color:#E74C3C; padding-bottom: 5px;'>{d}</div>", unsafe_allow_html=True)

    cal = calendar.monthcalendar(año_act, mes_act)
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                is_today = (date.today() == date(año_act, mes_act, day))
                btn_type = "primary" if is_today else "secondary"
                if cols[i].button(str(day), key=f"d_{año_act}_{mes_act}_{day}", use_container_width=True, type=btn_type):
                    st.session_state.app_fecha_sel = date(año_act, mes_act, day)
                    st.session_state.app_vista = "dia"
                    st.rerun()
            else: cols[i].write("")

    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.button("🎯 Ir directamente a las clases de Hoy", on_click=ir_a_hoy, use_container_width=True, type="primary")

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

    # --- FUNCIONES ---
    def cargar_datos_clases(fecha):
        df_completo = cargar_tabla("Clases")
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_dia = df_completo[df_completo['Fecha'] == fecha]
            if not df_dia.empty: 
                if 'Abono ($)' not in df_dia.columns: df_dia['Abono ($)'] = ""
                return df_dia.drop(columns=['Fecha']).reset_index(drop=True)
        return pd.DataFrame({
            "Hora": horas_30_min, "Estudiante": [""] * len(horas_30_min), "Modalidad / Motivo": [""] * len(horas_30_min),
            "Dirección": [""] * len(horas_30_min), "Minutos de Viaje": [0] * len(horas_30_min), 
            "Hora de Salida": [""] * len(horas_30_min), "Ruta Maps": [""] * len(horas_30_min), "Alarma": [""] * len(horas_30_min),
            "Estado": ["Libre 🟢"] * len(horas_30_min), "N° Clase": [""] * len(horas_30_min), "Pago": ["-"] * len(horas_30_min),
            "Abono ($)": [""] * len(horas_30_min), "Recordatorio": [""] * len(horas_30_min)
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
            geolocator = Nominatim(user_agent="clases_ingles_agenda", timeout=5)
            if isinstance(origen_coords_o_texto, tuple): coords_1 = origen_coords_o_texto 
            else:
                loc_origen = geolocator.geocode(origen_coords_o_texto + ", Chile")
                if not loc_origen: return 0
                coords_1 = (loc_origen.latitude, loc_origen.longitude)
            loc_destino = geolocator.geocode(destino + ", Chile")
            if loc_destino:
                coords_2 = (loc_destino.latitude, loc_destino.longitude)
                distancia_km = geodesic(coords_1, coords_2).kilometers
                minutos_estimados = int((distancia_km * 2.5) + 5)
                return minutos_estimados
        except Exception: pass
        return 0

    def obtener_lista_estudiantes():
        estudiantes = set()
        df_clases = cargar_tabla("Clases")
        if not df_clases.empty and 'Estudiante' in df_clases.columns:
            for p in df_clases['Estudiante'].dropna().unique():
                p_str = str(p).strip()
                if p_str != "" and p_str.upper() != "ALMUERZO": estudiantes.add(p_str.title()) 
        
        df_fichas = cargar_tabla("Estudiantes")
        if not df_fichas.empty and 'Estudiante' in df_fichas.columns:
            for p in df_fichas['Estudiante'].dropna().unique():
                p_str = str(p).strip()
                if p_str != "": estudiantes.add(p_str.title()) 
                
        return sorted(list(estudiantes))

    def calcular_estadisticas_globales(nombre_estudiante):
        nombre_norm = str(nombre_estudiante).strip().upper()
        df_completo = cargar_tabla("Clases")
        if df_completo.empty or 'Estudiante' not in df_completo.columns: return 0, 0, 0
        df_est = df_completo[(df_completo['Estudiante'].str.strip().str.upper() == nombre_norm) & (~df_completo['Modalidad / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))]
        tot_clases = len(df_est)
        pagadas = len(df_est[df_est['Pago'].isin(["Pagada ✅", "Pagada con Billetera ✅", "Pagada (Excedente) ✅"])])
        adeudadas = len(df_est[df_est['Pago'].isin(["No pagada ❌", "Abono Parcial ⏳"])])
        return tot_clases, pagadas, adeudadas

    def obtener_telefono_por_estudiante():
        df_fichas = cargar_tabla("Estudiantes")
        if df_fichas.empty or 'Estudiante' not in df_fichas.columns or 'Teléfono' not in df_fichas.columns: return {}
        return dict(zip(df_fichas['Estudiante'].astype(str).str.strip().str.upper(), df_fichas['Teléfono'].astype(str).str.strip()))
        
    def obtener_direccion_por_estudiante():
        df_fichas = cargar_tabla("Estudiantes")
        if df_fichas.empty or 'Estudiante' not in df_fichas.columns or 'Dirección' not in df_fichas.columns: return {}
        return dict(zip(df_fichas['Estudiante'].astype(str).str.strip().str.upper(), df_fichas['Dirección'].astype(str).str.strip()))

    def obtener_valor_por_estudiante():
        df_fichas = cargar_tabla("Estudiantes")
        if df_fichas.empty or 'Estudiante' not in df_fichas.columns or 'Valor Clase Presencial' not in df_fichas.columns: return {}
        mapa = {}
        for nombre, valor in zip(df_fichas['Estudiante'].astype(str).str.strip().str.upper(), df_fichas['Valor Clase Presencial']):
            mapa[nombre] = parse_dinero(valor)
        return mapa

    def obtener_valor_online_por_estudiante():
        df_fichas = cargar_tabla("Estudiantes")
        if df_fichas.empty or 'Estudiante' not in df_fichas.columns or 'Valor Clase Online' not in df_fichas.columns: return {}
        mapa = {}
        for nombre, valor in zip(df_fichas['Estudiante'].astype(str).str.strip().str.upper(), df_fichas['Valor Clase Online']):
            mapa[nombre] = parse_dinero(valor)
        return mapa

    def construir_link_whatsapp(telefono, fecha_visual_str, hora_str):
        if not telefono or str(telefono).strip() == "": return ""
        solo_digitos = "".join(ch for ch in str(telefono) if ch.isdigit())
        if solo_digitos == "": return ""
        if not solo_digitos.startswith("56"): solo_digitos = "56" + solo_digitos.lstrip("0")
        mensaje = f"Hello! 👋 Te escribo para confirmar nuestra clase de inglés del {fecha_visual_str} a las {hora_str} hrs. See you soon!"
        texto_codificado = urllib.parse.quote(mensaje)
        return f"https://wa.me/{solo_digitos}?text={texto_codificado}"

    def calcular_dashboard_mensual(fecha_referencia):
        df_completo = cargar_tabla("Clases")
        resultado = {
            "total_sesiones": 0, "pagadas": 0, "adeudadas": 0, 
            "ingresos": 0.0, "por_cobrar": 0.0, 
            "ingresos_sesiones": 0.0, "ingresos_pautas": 0.0,
            "deuda_sesiones": 0.0, "deuda_pautas": 0.0,
            "pacientes_con_deuda": 0, "pacientes_totales": 0
        }
        if df_completo.empty or 'Fecha' not in df_completo.columns: return resultado
        prefijo_mes = fecha_referencia.strftime("%Y-%m")
        df_mes = df_completo[df_completo['Fecha'].astype(str).str.startswith(prefijo_mes)].copy()
        df_mes = df_mes[~df_mes['Modalidad / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"])]
        df_mes = df_mes[(df_mes['Estudiante'].astype(str).str.strip() != "") & (df_mes['Estudiante'].astype(str).str.strip().str.upper() != "ALMUERZO")]
        if df_mes.empty: return resultado
        
        mapa_valores_presencial = obtener_valor_por_estudiante()
        mapa_valores_online = obtener_valor_online_por_estudiante()
        df_mes['Estudiante_norm'] = df_mes['Estudiante'].astype(str).str.strip().str.upper()
        if 'Abono ($)' not in df_mes.columns: df_mes['Abono ($)'] = ""
        
        for index, row in df_mes.iterrows():
            est_norm = row['Estudiante_norm']
            es_online = (str(row['Modalidad / Motivo']).strip() == "Clase Online 💻")
            val_clase = mapa_valores_online.get(est_norm, 0.0) if es_online else mapa_valores_presencial.get(est_norm, 0.0)
            
            pago_estado = str(row['Pago']).strip()
            abono_val = parse_dinero(row['Abono ($)'])
            
            ingreso_hoy = 0.0
            deuda_hoy = 0.0
            pagada_count = 0
            adeudada_count = 0
            
            if pago_estado == "Pagada ✅":
                ingreso_hoy = abono_val if abono_val > 0 else val_clase
                pagada_count = 1
            elif pago_estado == "Pagada (Excedente) ✅":
                ingreso_hoy = abono_val
                pagada_count = 1
            elif pago_estado == "Pagada con Billetera ✅":
                ingreso_hoy = 0.0 # Dinero entró antes
                pagada_count = 1
            elif pago_estado == "Abono Parcial ⏳":
                ingreso_hoy = abono_val
                deuda_hoy = max(0.0, val_clase - abono_val)
                adeudada_count = 1
            elif pago_estado == "No pagada ❌":
                deuda_hoy = val_clase
                adeudada_count = 1
                
            resultado["total_sesiones"] += 1
            resultado["pagadas"] += pagada_count
            resultado["adeudadas"] += adeudada_count
            resultado["ingresos"] += ingreso_hoy
            resultado["por_cobrar"] += deuda_hoy
            
            if es_online:
                resultado["ingresos_pautas"] += ingreso_hoy
                resultado["deuda_pautas"] += deuda_hoy
            else:
                resultado["ingresos_sesiones"] += ingreso_hoy
                resultado["deuda_sesiones"] += deuda_hoy

        estudiantes_totales = df_mes['Estudiante_norm'].unique()
        estudiantes_deuda = df_mes[df_mes['Pago'].isin(["No pagada ❌", "Abono Parcial ⏳"])]['Estudiante_norm'].unique()
        resultado["pacientes_totales"] = len(estudiantes_totales)
        resultado["pacientes_con_deuda"] = len(estudiantes_deuda)
        return resultado

    def calcular_sesion_historica(nombre_estudiante, fecha_actual, hora_actual):
        if nombre_estudiante == "": return ""
        nombre_norm = str(nombre_estudiante).strip().upper()
        df_completo = cargar_tabla("Clases")
        if df_completo.empty or 'Estudiante' not in df_completo.columns: return "1"
        df_hist = df_completo[(df_completo['Estudiante'].str.strip().str.upper() == nombre_norm) & (~df_completo['Modalidad / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))].copy()
        if df_hist.empty: return "1"
        df_hist['FechaHora'] = pd.to_datetime(df_hist['Fecha'] + ' ' + df_hist['Hora'])
        fecha_hora_actual = pd.to_datetime(f"{fecha_actual} {hora_actual}")
        contador = len(df_hist[df_hist['FechaHora'] <= fecha_hora_actual])
        return str(contador if contador > 0 else 1)

    # --- CARGA DE DATOS ---
    df_clases = cargar_datos_clases(fecha_str)
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
                    if idx < len(df_clases): df_clases.at[idx, 'Hora'] = f"🔴 {h_str}"
                    if idx < len(df_personal): df_personal.at[idx, 'Hora'] = f"🔴 {h_str}"
                    break
        except: pass

    df_clases['Estudiante'] = df_clases['Estudiante'].fillna("") 
    df_clases['Dirección'] = df_clases['Dirección'].fillna("").astype(str)
    df_clases['Minutos de Viaje'] = pd.to_numeric(df_clases['Minutos de Viaje'], errors='coerce').fillna(0).astype(int)
    df_clases['Hora de Salida'] = df_clases['Hora de Salida'].fillna("").astype(str)
    df_clases['Ruta Maps'] = df_clases['Ruta Maps'].fillna("").astype(str)
    if 'Alarma' not in df_clases.columns: df_clases['Alarma'] = ""
    df_clases['Alarma'] = df_clases['Alarma'].fillna("").astype(str)
    df_clases['N° Clase'] = df_clases['N° Clase'].fillna("").astype(str)
    df_clases['Pago'] = df_clases['Pago'].fillna("-").astype(str)
    if 'Abono ($)' not in df_clases.columns: df_clases['Abono ($)'] = ""
    df_clases['Abono ($)'] = df_clases['Abono ($)'].fillna("").astype(str)
    if 'Recordatorio' not in df_clases.columns: df_clases['Recordatorio'] = ""
    df_clases['Recordatorio'] = df_clases['Recordatorio'].fillna("").astype(str)

    df_personal['Actividad'] = df_personal['Actividad'].fillna("").astype(str)
    df_personal['Categoría'] = df_personal['Categoría'].fillna("-").astype(str)
    df_personal['Notas'] = df_personal['Notas'].fillna("").astype(str)

    # MAPEO SEGURO POR HORA
    mapa_estudiantes_clases = {}
    for _, row_c in df_clases.iterrows():
        h_limp = str(row_c['Hora']).replace("🔴 ", "").replace("🔴", "").strip()
        p_val = str(row_c['Estudiante']).strip()
        if p_val != "" and p_val.upper() != "ALMUERZO":
            mapa_estudiantes_clases[h_limp] = p_val

    for idx_p in df_personal.index:
        h_pers = str(df_personal.at[idx_p, 'Hora']).replace("🔴 ", "").replace("🔴", "").strip()
        act_personal = str(df_personal.at[idx_p, 'Actividad']).strip()
        if h_pers in mapa_estudiantes_clases:
            est_clase = mapa_estudiantes_clases[h_pers]
            if not act_personal.startswith("👩‍🏫 Clase:"):
                df_personal.at[idx_p, 'Actividad'] = f"👩‍🏫 Clase: {est_clase}"
                df_personal.at[idx_p, 'Categoría'] = "Clases"
        else:
            if act_personal.startswith("👩‍🏫 Clase:"):
                df_personal.at[idx_p, 'Actividad'] = ""
                df_personal.at[idx_p, 'Categoría'] = "-"

    mapa_personal = obtener_actividad_por_hora(df_personal) 
    mapa_telefonos = obtener_telefono_por_estudiante()
    mapa_direcciones = obtener_direccion_por_estudiante()

    opciones_motivo = ["Clase a Domicilio 🏠", "Clase en mi Casa 🏫", "Clase Online 💻", "Evaluación 📝", "Personal / Trámite 🛑", "Gimnasio 🏋️", "-"]

    for index in df_clases.index:
        estudiante = str(df_clases.at[index, 'Estudiante']).strip()
        direccion = str(df_clases.at[index, 'Dirección']).strip()
        hora_str = str(df_clases.at[index, 'Hora']).replace("🔴 ", "").replace("🔴", "").strip()
        minutos = int(df_clases.at[index, 'Minutos de Viaje'])
        pago_actual = str(df_clases.at[index, 'Pago']).strip()
        clase_actual = str(df_clases.at[index, 'N° Clase']).strip()
        detalle_actual = str(df_clases.at[index, 'Modalidad / Motivo']).strip()
        actividad_personal = mapa_personal.get(hora_str, "") 
        es_tramite = (detalle_actual == "Personal / Trámite 🛑")
        es_gimnasio = (detalle_actual == "Gimnasio 🏋️")
        es_clase = (detalle_actual in ["Clase a Domicilio 🏠", "Clase en mi Casa 🏫", "Clase Online 💻", "Evaluación 📝"])
        es_almuerzo = (estudiante.upper() == "ALMUERZO")
        hay_estudiante = (estudiante != "" and not es_almuerzo)
        
        # MAGIA: Si no tiene dirección en la tabla, la saca de la ficha
        if hay_estudiante and direccion == "":
            dir_guardada = mapa_direcciones.get(estudiante.upper(), "")
            if dir_guardada != "":
                direccion = dir_guardada
                df_clases.at[index, 'Dirección'] = direccion

        if hay_estudiante or es_tramite or es_gimnasio or es_clase:
            if direccion != "" and direccion != "-":
                query_maps = urllib.parse.quote(direccion + ", Chile")
                df_clases.at[index, 'Ruta Maps'] = f"https://www.google.com/maps/search/?api=1&query={query_maps}"
            else: df_clases.at[index, 'Ruta Maps'] = ""
            
            if minutos > 0 and detalle_actual != "Clase Online 💻":
                try:
                    tiempo_agendado = datetime.strptime(hora_str, "%H:%M")
                    tiempo_salida = tiempo_agendado - timedelta(minutes=(minutos + 5))
                    df_clases.at[index, 'Hora de Salida'] = tiempo_salida.strftime("%H:%M")
                    formato_fecha = fecha_str.replace("-", "")
                    h_ini = tiempo_salida.strftime("%H%M%S")
                    h_fin = tiempo_agendado.strftime("%H%M%S")
                    txt_ev = urllib.parse.quote(f"🚗 VIAJE: {estudiante if hay_estudiante else detalle_actual}")
                    dest = urllib.parse.quote(direccion if direccion != "" else "Destino")
                    df_clases.at[index, 'Alarma'] = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={txt_ev}&dates={formato_fecha}T{h_ini}/{formato_fecha}T{h_fin}&details=Hora+de+salir+hacia:+{dest}"
                except:
                    df_clases.at[index, 'Hora de Salida'] = ""
                    df_clases.at[index, 'Alarma'] = ""
            else:
                df_clases.at[index, 'Hora de Salida'] = ""
                df_clases.at[index, 'Alarma'] = ""

            if es_tramite or es_gimnasio:
                df_clases.at[index, 'Pago'] = "-"
                df_clases.at[index, 'N° Clase'] = "-"
            else:
                if pago_actual == "-" or pago_actual == "": df_clases.at[index, 'Pago'] = "No pagada ❌"
                es_numero_auto = False
                if clase_actual == "" or clase_actual == "-" or clase_actual == "Online": es_numero_auto = True
                else:
                    try: float(clase_actual); es_numero_auto = True
                    except ValueError: es_numero_auto = False
                
                if es_numero_auto: 
                    df_clases.at[index, 'N° Clase'] = calcular_sesion_historica(estudiante, fecha_str, hora_str)
                        
            if hay_estudiante:
                telefono_estudiante = mapa_telefonos.get(estudiante.strip().upper(), "")
                df_clases.at[index, 'Recordatorio'] = construir_link_whatsapp(telefono_estudiante, fecha_visual, hora_str)
            else: df_clases.at[index, 'Recordatorio'] = ""
        else:
            df_clases.at[index, 'Ruta Maps'] = ""; df_clases.at[index, 'Hora de Salida'] = ""; df_clases.at[index, 'Alarma'] = ""
            df_clases.at[index, 'N° Clase'] = ""; df_clases.at[index, 'Pago'] = "-"; df_clases.at[index, 'Recordatorio'] = ""

        if actividad_personal != "" and (hay_estudiante or es_clase):
            if actividad_personal.startswith("👩‍🏫 Clase:"): df_clases.at[index, 'Estado'] = "Agendado 🔒"
            else: df_clases.at[index, 'Estado'] = "⚠️ TOPE HORARIO ⚠️"
        elif actividad_personal != "": df_clases.at[index, 'Estado'] = f"Bloqueado ({actividad_personal}) 🛑"
        elif es_tramite: df_clases.at[index, 'Estado'] = "Bloqueado 🛑"
        elif es_gimnasio: df_clases.at[index, 'Estado'] = "Gimnasio 🏋️"
        elif es_clase or hay_estudiante: df_clases.at[index, 'Estado'] = "Agendado 🔒"
        elif es_almuerzo: df_clases.at[index, 'Estado'] = "-"
        else:
            if index > 0:
                estudiante_ant = str(df_clases.at[index - 1, 'Estudiante']).strip()
                detalle_ant = str(df_clases.at[index - 1, 'Modalidad / Motivo']).strip()
                if (detalle_ant == "Personal / Trámite 🛑") or (detalle_ant == "Gimnasio 🏋️"):
                    df_clases.at[index, 'Estado'] = f"Bloqueado ({estudiante_ant if estudiante_ant != '' else ('Trámite' if detalle_ant == 'Personal / Trámite 🛑' else 'Gimnasio')}) ⏳"
                    continue
                elif (detalle_ant in ["Clase a Domicilio 🏠", "Clase en mi Casa 🏫", "Clase Online 💻", "Evaluación 📝"]) or (estudiante_ant != "" and estudiante_ant.upper() != "ALMUERZO"):
                    df_clases.at[index, 'Estado'] = f"En clase ({estudiante_ant if estudiante_ant != '' else 'Estudiante'}) ⏳"
                    continue
            df_clases.at[index, 'Estado'] = "Libre 🟢"

    # --- PESTAÑAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📚 Agenda Diaria", "🕰️ Horario Personal", "📁 Expedientes (Alumnos)", "📊 Finanzas"])

    with tab1:
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1: 
            st.header(f"📅 Agenda de Clases - {fecha_visual}")
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
                            if h_obj_b > hora_actual_time and i_h < len(df_clases) and i_h < len(df_personal):
                                est_b = str(df_clases.at[i_h, 'Estudiante']).strip()
                                mot_b = str(df_clases.at[i_h, 'Modalidad / Motivo']).strip()
                                act_b = str(df_personal.at[i_h, 'Actividad']).strip()
                                
                                evento_b = ""
                                if est_b != "" and est_b.upper() != "ALMUERZO":
                                    evento_b = f"Estudiante: {est_b}"
                                elif mot_b in ["Gimnasio 🏋️", "Personal / Trámite 🛑"]:
                                    evento_b = mot_b.replace(' 🏋️', '').replace(' 🛑', '')
                                elif est_b.upper() == "ALMUERZO":
                                    evento_b = "Almuerzo"
                                elif act_b != "":
                                    evento_b = act_b.replace("👩‍🏫 Clase: ", "Estudiante: ")
                                    
                                if evento_b != "":
                                    hora_evento_dt = ahora_chile.replace(hour=h_obj_b.hour, minute=h_obj_b.minute, second=0, microsecond=0)
                                    mins_faltantes = int((hora_evento_dt - ahora_chile).total_seconds() / 60)
                                    texto_proximo = f"<div style='margin-top: 15px; padding-top: 12px; border-top: 1px dashed #bdc3c7;'><span style='color: #e67e22; font-size: 0.95rem; font-weight: bold;'>👉 Próximo a las {h_str_b}: {evento_b} (en {mins_faltantes} min)</span></div>"
                                    break
                                    
                        if texto_proximo == "":
                            texto_proximo = "<div style='margin-top: 15px; padding-top: 12px; border-top: 1px dashed #bdc3c7;'><span style='color: #18BC9C; font-size: 0.95rem; font-weight: bold;'>👉 No hay más clases agendadas. ¡Día terminado! 🎉</span></div>"

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
            btn_guardar_clases = st.button("💾 Guardar Cambios", use_container_width=True, type="primary", key="btn_save_clases")
        
        with st.expander("⚡ Agendar Existente / Programar Clases / Reagendar"):
            tab_ex, tab_ag, tab_re = st.tabs(["➕ Estudiante Existente", "🔄 Múltiples Clases", "✂️ Reagendar"])
            
            with tab_ex:
                lista_est = obtener_lista_estudiantes()
                if not lista_est:
                    st.info("Primero agrega un estudiante manualmente en la tabla inferior o en Expedientes.")
                else:
                    col_e1, col_e2, col_e3 = st.columns(3)
                    with col_e1:
                        est_ex = st.selectbox("1. Estudiante Existente:", ["-- Selecciona --"] + lista_est)
                        mot_ex = st.selectbox("Modalidad:", opciones_motivo[:-2], key="mot_ex")
                    with col_e2:
                        hora_ex = st.selectbox(f"2. Hora (para este día):", horas_30_min, key="hora_ex")
                    with col_e3:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        btn_ex = st.button("🚀 Agendar en esta hora", use_container_width=True)
                    if btn_ex:
                        if est_ex == "-- Selecciona --": st.error("Por favor selecciona un estudiante.")
                        else:
                            idx_ex = df_clases.index[df_clases['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_ex].tolist()[0]
                            if str(df_clases.at[idx_ex, 'Estudiante']).strip() != "": st.error("⚠️ Esta hora ya está ocupada.")
                            else:
                                with st.spinner("Agendando..."):
                                    df_clases.at[idx_ex, 'Estudiante'] = est_ex
                                    df_clases.at[idx_ex, 'Modalidad / Motivo'] = mot_ex
                                    df_clases.at[idx_ex, 'Dirección'] = mapa_direcciones.get(est_ex.upper(), "") if mot_ex != "Clase en mi Casa 🏫" else ""
                                    df_clases.at[idx_ex, 'Minutos de Viaje'] = 0
                                    df_clases.at[idx_ex, 'Pago'] = "No pagada ❌"
                                    df_clases.at[idx_ex, 'N° Clase'] = ""
                                    guardar_dia("Clases", fecha_str, df_clases)
                                    st.success(f"✅ ¡{est_ex} agendado a las {hora_ex}!")
                                    time.sleep(1)
                                    st.rerun()

            with tab_ag:
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    m_estudiante = st.text_input("Estudiante:")
                    m_motivo = st.selectbox("Modalidad:", opciones_motivo[:-2])
                    m_clases = st.number_input("N° de clases a programar:", min_value=1, value=4, step=1)
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
                    if m_estudiante.strip() == "": st.error("Ingresa el estudiante.")
                    elif not m_dias: st.error("Selecciona días.")
                    else:
                        sesiones_logradas, dias_buscados = 0, 0
                        fecha_iter, dias_obj = m_fecha_inicio, [dias_map[d] for d in m_dias]
                        fechas_exitosas, fechas_ocupadas = [], []
                        with st.spinner('Agendando...'):
                            while sesiones_logradas < m_clases and dias_buscados < 365:
                                if fecha_iter.weekday() in dias_obj:
                                    f_str = fecha_iter.strftime("%Y-%m-%d")
                                    df_dia_futuro = cargar_datos_clases(f_str)
                                    df_pers_futuro = cargar_datos_personal(f_str)
                                    mapa_personal_futuro = obtener_actividad_por_hora(df_pers_futuro) 
                                    idx_hora = df_dia_futuro.index[df_dia_futuro['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == m_hora].tolist()
                                    if idx_hora:
                                        idx = idx_hora[0]
                                        p_act = str(df_dia_futuro.at[idx, 'Estudiante']).strip()
                                        d_act = str(df_dia_futuro.at[idx, 'Modalidad / Motivo']).strip()
                                        a_act = mapa_personal_futuro.get(m_hora, "")
                                        ocupado = True if p_act != "" or d_act in ["Personal / Trámite 🛑", "Gimnasio 🏋️"] or (a_act != "" and not a_act.startswith("👩‍🏫")) else False
                                        if not ocupado:
                                            df_dia_futuro.at[idx, 'Estudiante'] = m_estudiante
                                            df_dia_futuro.at[idx, 'Modalidad / Motivo'] = m_motivo
                                            dir_final = m_direccion
                                            if dir_final == "": dir_final = mapa_direcciones.get(m_estudiante.strip().upper(), "")
                                            df_dia_futuro.at[idx, 'Dirección'] = dir_final
                                            df_dia_futuro.at[idx, 'Minutos de Viaje'] = m_viaje
                                            df_dia_futuro.at[idx, 'Pago'] = "No pagada ❌"
                                            df_dia_futuro.at[idx, 'N° Clase'] = "" 
                                            exito_agendar = guardar_dia("Clases", f_str, df_dia_futuro)
                                            if exito_agendar:
                                                fechas_exitosas.append(fecha_iter.strftime("%d/%m/%Y"))
                                                sesiones_logradas += 1
                                                time.sleep(0.3)
                                        else: fechas_ocupadas.append(fecha_iter.strftime("%d/%m/%Y"))
                                fecha_iter += timedelta(days=1)
                                dias_buscados += 1
                                
                            if sesiones_logradas > 0 and m_direccion.strip() != "":
                                df_fichas_sync = cargar_tabla("Estudiantes")
                                if df_fichas_sync.empty or 'Estudiante' not in df_fichas_sync.columns:
                                    df_fichas_sync = pd.DataFrame(columns=['Estudiante', 'Teléfono', 'Edad', 'Nivel de Inglés', 'Notas (Evaluaciones)', 'Historial de Clases', 'Valor Clase Presencial', 'Dirección', 'Valor Clase Online', 'Billetera'])
                                if 'Dirección' not in df_fichas_sync.columns: df_fichas_sync['Dirección'] = ""
                                if 'Valor Clase Online' not in df_fichas_sync.columns: df_fichas_sync['Valor Clase Online'] = ""
                                if 'Billetera' not in df_fichas_sync.columns: df_fichas_sync['Billetera'] = 0.0
                                
                                mask_f = df_fichas_sync['Estudiante'].astype(str).str.strip().str.upper() == m_estudiante.strip().upper()
                                if mask_f.any():
                                    idx_f = df_fichas_sync[mask_f].index[0]
                                    if str(df_fichas_sync.at[idx_f, 'Dirección']).strip() != m_direccion.strip():
                                        df_fichas_sync.at[idx_f, 'Dirección'] = m_direccion.strip()
                                        guardar_tabla("Estudiantes", df_fichas_sync)
                                else:
                                    nueva_fila = pd.DataFrame({'Estudiante': [m_estudiante.strip().title()], 'Teléfono': [""], 'Edad': [""], 'Nivel de Inglés': [""], 'Notas (Evaluaciones)': [""], 'Historial de Clases': [""], 'Valor Clase Presencial': [""], 'Dirección': [m_direccion.strip()], 'Valor Clase Online': [""], 'Billetera': [0.0]})
                                    df_fichas_sync = pd.concat([df_fichas_sync, nueva_fila], ignore_index=True)
                                    guardar_tabla("Estudiantes", df_fichas_sync)

                        if sesiones_logradas == m_clases: st.success("✅ ¡Agendado!")
                        else: st.warning(f"⚠️ Solo se agendaron {sesiones_logradas}.")
                        st.rerun()

            with tab_re:
                sesiones_activas = df_clases[(df_clases['Estudiante'].str.strip() != "") & (df_clases['Estudiante'].str.upper() != "ALMUERZO")]
                opciones_citas = ["-- Selecciona --"] + [f"{str(r['Hora']).replace('🔴 ', '')} - {r['Estudiante']}" for i, r in sesiones_activas.iterrows()]
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    cita_origen = st.selectbox("Clase de hoy:", opciones_citas)
                    accion_reagendar = st.radio("Acción:", ["Mover", "Duplicar"])
                with col_r2:
                    fecha_destino = st.date_input("Nueva fecha:", value=st.session_state.app_fecha_sel + timedelta(days=1))
                    hora_destino = st.selectbox("Nueva hora:", horas_30_min, key="hora_destino_reagendar")
                with col_r3:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    btn_reagendar = st.button("🚀 Ejecutar", use_container_width=True)
                if btn_reagendar and cita_origen != "-- Selecciona --":
                    hora_origen = cita_origen.split(" - ")[0].replace("🔴 ", "").replace("🔴", "").strip()
                    idx_origen_list = df_clases.index[df_clases['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_origen].tolist()
                    if idx_origen_list:
                        fila_origen = df_clases.iloc[idx_origen_list[0]]
                        f_dest_str = fecha_destino.strftime("%Y-%m-%d")
                        df_clases_dest = cargar_datos_clases(f_dest_str)
                        idx_dest = df_clases_dest.index[df_clases_dest['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_destino].tolist()[0]
                        if str(df_clases_dest.at[idx_dest, 'Estudiante']).strip() != "":
                            st.error("⚠️ La hora de destino está ocupada.")
                        else:
                            with st.spinner("Procesando..."):
                                df_clases_dest.at[idx_dest, 'Estudiante'] = str(fila_origen['Estudiante'])
                                df_clases_dest.at[idx_dest, 'Modalidad / Motivo'] = str(fila_origen['Modalidad / Motivo'])
                                df_clases_dest.at[idx_dest, 'Dirección'] = str(fila_origen['Dirección'])
                                df_clases_dest.at[idx_dest, 'Minutos de Viaje'] = int(fila_origen['Minutos de Viaje'])
                                df_clases_dest.at[idx_dest, 'Pago'] = "No pagada ❌"
                                df_clases_dest.at[idx_dest, 'N° Clase'] = "" 
                                exito_r = guardar_dia("Clases", f_dest_str, df_clases_dest)
                                if exito_r and accion_reagendar == "Mover":
                                    idx_origen = df_clases.index[df_clases['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_origen].tolist()[0]
                                    df_clases.at[idx_origen, 'Estudiante'] = ""
                                    df_clases.at[idx_origen, 'Modalidad / Motivo'] = "-"
                                    df_clases.at[idx_origen, 'Dirección'] = ""
                                    df_clases.at[idx_origen, 'Minutos de Viaje'] = 0
                                    df_clases.at[idx_origen, 'Pago'] = "-"
                                    df_clases.at[idx_origen, 'N° Clase'] = ""
                                    guardar_dia("Clases", fecha_str, df_clases)
                                if exito_r:
                                    st.success("✅ ¡Listo!")
                                    time.sleep(1)
                                    st.rerun()

        with st.expander("🔍 Buscador de Estudiantes"):
            lista_est_buscador = obtener_lista_estudiantes()
            if not lista_est_buscador: st.info("No hay estudiantes agendados.")
            else:
                estudiante_buscar = st.selectbox("Selecciona un estudiante:", ["-- Selecciona --"] + lista_est_buscador, key="buscador_paciente_cal")
                if estudiante_buscar != "-- Selecciona --":
                    df_full_clases = cargar_tabla("Clases")
                    if not df_full_clases.empty and 'Estudiante' in df_full_clases.columns:
                        df_filtro = df_full_clases[df_full_clases['Estudiante'].astype(str).str.strip().str.upper() == estudiante_buscar.upper()]
                        if not df_filtro.empty:
                            df_resumen = df_filtro[['Fecha', 'Hora', 'Modalidad / Motivo', 'Estado', 'Pago']].sort_values(by=['Fecha', 'Hora'])
                            st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                            
                            st.markdown("🎯 **Ir directamente al día para editar:**")
                            col_b1, col_b2 = st.columns([3, 1])
                            with col_b1:
                                opciones_sesiones = ["-- Elige una clase --"] + [f"{r['Fecha']} a las {r['Hora']} ({r['Pago']})" for i, r in df_resumen.iterrows()]
                                sesion_a_editar = st.selectbox("Seleccionar clase", opciones_sesiones, label_visibility="collapsed")
                            with col_b2:
                                if st.button("🚀 Viajar al Día", use_container_width=True):
                                    if sesion_a_editar != "-- Elige una clase --":
                                        fecha_destino_str = sesion_a_editar.split(" a las ")[0]
                                        try:
                                            fecha_obj = datetime.strptime(fecha_destino_str, "%Y-%m-%d").date()
                                            st.session_state.app_fecha_sel = fecha_obj
                                            st.session_state.app_mes_cal = fecha_obj.replace(day=1)
                                            st.session_state.app_vista = "dia"
                                            st.rerun()
                                        except: pass
                                    else: st.error("Selecciona una cita válida de la lista.")
                        else: st.warning("No se encontraron clases.")

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
                            
                            for idx, row in df_clases.iterrows():
                                est = str(row['Estudiante']).strip()
                                motivo = str(row['Modalidad / Motivo']).strip()
                                
                                if est != "" and est.upper() != "ALMUERZO":
                                    hora = str(row['Hora']).replace("🔴", "").strip()
                                    direccion = str(row['Dirección']).strip()
                                    min_viaje = int(row['Minutos de Viaje'])
                                    
                                    h_ini = datetime.strptime(f"{fecha_str} {hora}", "%Y-%m-%d %H:%M")
                                    h_fin = h_ini + timedelta(minutes=60) # Asumiendo clases de 60 mins
                                    minutos_aviso = 30 + min_viaje
                                    
                                    evento = {
                                        'summary': f'👩‍🏫 Inglés: {est}',
                                        'location': direccion if motivo != "Clase Online 💻" else "Videollamada",
                                        'description': f'Modalidad: {motivo}',
                                        'start': {'dateTime': h_ini.strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': 'America/Santiago'},
                                        'end': {'dateTime': h_fin.strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': 'America/Santiago'},
                                        'reminders': {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': minutos_aviso}]},
                                    }
                                    service.events().insert(calendarId=correo_cal, body=evento).execute()
                                    eventos_creados += 1
                            if eventos_creados > 0:
                                st.success(f"✅ ¡Éxito! Se crearon {eventos_creados} eventos en tu Google Calendar para hoy.")
                            else:
                                st.info("No hay clases agendadas para sincronizar hoy.")
                    except ImportError:
                        st.error("🚨 Falta instalar la librería. Ve a tu GitHub y agrega `google-api-python-client` en tu archivo `requirements.txt`.")
                    except Exception as e:
                        st.error(f"🚨 Error de permisos con Google: {e}")

        with st.expander("📍 Viajes y Tiempos"):
            ubicacion_gps = streamlit_geolocation()
            direccion_base = st.text_input("O escribe tu domicilio / base:", value="Viña del Mar")
            if st.button("⚡ Calcular Tiempos Automáticos de Hoy"):
                with st.spinner("Calculando..."):
                    origen_final = direccion_base
                    fallos = 0
                    if ubicacion_gps and ubicacion_gps.get('latitude') is not None: origen_final = (ubicacion_gps['latitude'], ubicacion_gps['longitude'])
                    for idx in df_clases.index:
                        dir_est, hora_est = str(df_clases.at[idx, 'Dirección']).strip(), str(df_clases.at[idx, 'Hora']).replace("🔴 ", "").replace("🔴", "").strip()
                        if dir_est != "" and str(df_clases.at[idx, 'Modalidad / Motivo']).strip() not in ["Clase en mi Casa 🏫", "Clase Online 💻"]:
                            minutos_gps = calcular_tiempo_gps(origen_final, dir_est)
                            if minutos_gps > 0: df_clases.at[idx, 'Minutos de Viaje'] = minutos_gps
                            else: fallos += 1
                    exito = guardar_dia("Clases", fecha_str, df_clases)
                    if exito: 
                        if fallos > 0: st.warning(f"Se calculó, pero el mapa falló en {fallos} dirección(es). Pon los minutos manualmente.")
                        else: st.success("¡Calculado!")
                    st.rerun()

        st.caption("💡 Tip: Escribe en la columna **Abono ($)** si te transfieren más o menos del costo de la clase. Si es más, el excedente se guardará en su Billetera.")
        df_clases_editado = st.data_editor(
            df_clases, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"editor_clinica_{fecha_str}",
            column_order=("Hora", "Estudiante", "Modalidad / Motivo", "Dirección", "Minutos de Viaje", "Hora de Salida", "Ruta Maps", "Recordatorio", "Estado", "N° Clase", "Pago", "Abono ($)"),
            column_config={
                "Hora": st.column_config.TextColumn("Hora", disabled=True),
                "Modalidad / Motivo": st.column_config.SelectboxColumn("Modalidad", options=opciones_motivo),
                "Dirección": st.column_config.TextColumn("Dirección"),
                "Minutos de Viaje": st.column_config.NumberColumn("Min. Viaje", min_value=0, step=1),
                "Hora de Salida": st.column_config.TextColumn("Salida", disabled=True),
                "Ruta Maps": st.column_config.LinkColumn("🗺️ Mapa", disabled=True, display_text="Ver Mapa"),
                "Recordatorio": st.column_config.LinkColumn("📲 WhatsApp", disabled=True, display_text="Enviar"),
                "Estado": st.column_config.TextColumn("Estado", disabled=True),
                "N° Clase": st.column_config.TextColumn("N° Clase", help="Calculado auto."),
                "Pago": st.column_config.SelectboxColumn("Pago", options=["No pagada ❌", "Pagada ✅", "Abono Parcial ⏳", "Descontar Billetera 💳", "Pagada con Billetera ✅", "Pagada (Excedente) ✅", "-"]),
                "Abono ($)": st.column_config.TextColumn("Abono ($)", help="Escribe números sin puntos si pagó algo distinto al valor")
            }
        )
        if btn_guardar_clases:
            df_fichas_sync = cargar_tabla("Estudiantes")
            if df_fichas_sync.empty or 'Estudiante' not in df_fichas_sync.columns:
                df_fichas_sync = pd.DataFrame(columns=['Estudiante', 'Teléfono', 'Edad', 'Nivel de Inglés', 'Notas (Evaluaciones)', 'Historial de Clases', 'Valor Clase Presencial', 'Dirección', 'Valor Clase Online', 'Billetera'])
            
            # Asegurar columnas nuevas
            for col in ['Dirección', 'Valor Clase Online', 'Notas (Evaluaciones)']:
                if col not in df_fichas_sync.columns: df_fichas_sync[col] = ""
            if 'Billetera' not in df_fichas_sync.columns: df_fichas_sync['Billetera'] = 0.0
            
            df_fichas_sync['Billetera'] = pd.to_numeric(df_fichas_sync['Billetera'], errors='coerce').fillna(0.0)
            
            cambios_fichas = False
            mapa_val = obtener_valor_por_estudiante()
            mapa_pau = obtener_valor_online_por_estudiante()
            
            # MAGIA CONTABLE: PROCESAR BILLETERAS Y ABONOS ANTES DE GUARDAR
            for idx, r in df_clases_editado.iterrows():
                pac = str(r['Estudiante']).strip()
                dir_cal = str(r['Dirección']).strip()
                if pac != "" and pac.upper() != "ALMUERZO":
                    
                    # 1. Sincronizar Fichas nuevas o Direcciones
                    mask_f = df_fichas_sync['Estudiante'].astype(str).str.strip().str.upper() == pac.upper()
                    if mask_f.any():
                        idx_f = df_fichas_sync[mask_f].index[0]
                        if dir_cal != "" and dir_cal != "-" and str(df_fichas_sync.at[idx_f, 'Dirección']).strip() != dir_cal:
                            df_fichas_sync.at[idx_f, 'Dirección'] = dir_cal
                            cambios_fichas = True
                    elif dir_cal != "" and dir_cal != "-":
                        nueva_fila = pd.DataFrame({'Estudiante': [pac.title()], 'Teléfono': [""], 'Edad': [""], 'Nivel de Inglés': [""], 'Notas (Evaluaciones)': [""], 'Historial de Clases': [""], 'Valor Clase Presencial': [""], 'Dirección': [dir_cal], 'Valor Clase Online': [""], 'Billetera': [0.0]})
                        df_fichas_sync = pd.concat([df_fichas_sync, nueva_fila], ignore_index=True)
                        cambios_fichas = True
                        idx_f = df_fichas_sync.index[-1]
                    else:
                        continue # No hay estudiante en ficha y no hay dirección, saltamos
                        
                    # 2. Lógica de Billetera y Pagos
                    pago_est = str(r['Pago']).strip()
                    abono_val = parse_dinero(r['Abono ($)'])
                    motivo = str(r['Modalidad / Motivo']).strip()
                    val_ses = mapa_pau.get(pac.upper(), 0.0) if motivo == "Clase Online 💻" else mapa_val.get(pac.upper(), 0.0)
                    
                    billetera_act = float(df_fichas_sync.at[idx_f, 'Billetera'])
                    
                    # Caso A: Quiere descontar de la billetera
                    if pago_est == "Descontar Billetera 💳":
                        necesita = val_ses - abono_val # Por si paga una parte en cash y el resto billetera
                        if necesita > 0:
                            if billetera_act >= necesita:
                                df_fichas_sync.at[idx_f, 'Billetera'] = billetera_act - necesita
                                df_clases_editado.at[idx, 'Pago'] = "Pagada con Billetera ✅"
                                st.toast(f"💳 Se descontaron ${necesita:,.0f} de la billetera de {pac}")
                                cambios_fichas = True
                            else:
                                st.error(f"⚠️ {pac} solo tiene ${billetera_act:,.0f} a favor. No alcanza para descontar ${necesita:,.0f}.")
                                df_clases_editado.at[idx, 'Pago'] = "No pagada ❌"
                        else:
                            df_clases_editado.at[idx, 'Pago'] = "Pagada ✅"
                            
                    # Caso B: Pagó de más (Genera Excedente a Billetera)
                    elif pago_est not in ["Pagada (Excedente) ✅", "Pagada con Billetera ✅", "Descontar Billetera 💳"] and abono_val > val_ses and val_ses > 0:
                        excedente = abono_val - val_ses
                        df_fichas_sync.at[idx_f, 'Billetera'] = billetera_act + excedente
                        df_clases_editado.at[idx, 'Pago'] = "Pagada (Excedente) ✅"
                        st.toast(f"💰 Se guardaron ${excedente:,.0f} de excedente en la billetera de {pac}")
                        cambios_fichas = True
                        
                    # Caso C: Pagó de menos (Abono Parcial Automático)
                    elif pago_est == "No pagada ❌" and 0 < abono_val < val_ses:
                        df_clases_editado.at[idx, 'Pago'] = "Abono Parcial ⏳"
            
            if cambios_fichas:
                guardar_tabla("Estudiantes", df_fichas_sync)

            exito1 = guardar_dia("Clases", fecha_str, df_clases_editado)
            exito2 = guardar_dia("Personal", fecha_str, df_personal)
            if exito1 and exito2:
                st.success("¡Agenda guardada y Finanzas sincronizadas!")
                time.sleep(1)
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
                    cat_b = st.selectbox("Categoría:", ["Preparación de Clases", "Corrección Pruebas", "Mascota", "Salud", "Ocio", "Trámites", "Clases", "General", "-"], key="cat_b")
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
                                if not str(df_personal.at[i, 'Actividad']).startswith("👩‍🏫 Clase:"):
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
                                if not str(df_personal.at[i, 'Actividad']).startswith("👩‍🏫 Clase:"):
                                    df_personal.at[i, 'Actividad'] = motivo_dia
                                    df_personal.at[i, 'Categoría'] = "General"
                            guardar_dia("Personal", fecha_str, df_personal)
                            st.success("✅ ¡Día bloqueado completo!")
                            time.sleep(1)
                            st.rerun()
                
                if btn_desbloquear_dia:
                    with st.spinner("Liberando el día..."):
                        for i in range(len(df_personal)):
                            if not str(df_personal.at[i, 'Actividad']).startswith("👩‍🏫 Clase:"):
                                df_personal.at[i, 'Actividad'] = ""
                                df_personal.at[i, 'Categoría'] = "-"
                        guardar_dia("Personal", fecha_str, df_personal)
                        st.success("✅ ¡Día liberado!")
                        time.sleep(1)
                        st.rerun()

        df_personal_editado = st.data_editor(
            df_personal, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"editor_personal_{fecha_str}",
            column_order=("Hora", "Actividad", "Categoría", "Notas"),
            column_config={
                "Hora": st.column_config.TextColumn("Hora", disabled=True),
                "Actividad": st.column_config.TextColumn("Actividad"),
                "Categoría": st.column_config.SelectboxColumn("Categoría", options=["Preparación de Clases", "Corrección Pruebas", "Mascota", "Salud", "Ocio", "Trámites", "Clases", "General", "-"]),
            }
        )
        if btn_guardar_personal:
            exito = guardar_dia("Personal", fecha_str, df_personal_editado)
            if exito:
                st.success("¡Guardado!")
                st.rerun()

    with tab3:
        st.header("📁 Expedientes (Alumnos)")
        
        with st.expander("➕ Crear Nuevo Estudiante", expanded=False):
            col_n1, col_n2 = st.columns([3, 1])
            with col_n1:
                nuevo_nombre_paciente = st.text_input("Nombre completo del nuevo estudiante:", key="input_nuevo_paciente")
            with col_n2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✨ Crear Expediente", use_container_width=True, type="primary"):
                    if nuevo_nombre_paciente.strip() == "":
                        st.error("Escribe un nombre.")
                    else:
                        nombre_limpio = nuevo_nombre_paciente.strip().title()
                        df_fichas_temp = cargar_tabla("Estudiantes")
                        if df_fichas_temp.empty or 'Estudiante' not in df_fichas_temp.columns:
                            df_fichas_temp = pd.DataFrame(columns=['Estudiante', 'Teléfono', 'Edad', 'Nivel de Inglés', 'Notas (Evaluaciones)', 'Historial de Clases', 'Valor Clase Presencial', 'Dirección', 'Valor Clase Online', 'Billetera'])
                        
                        if 'Valor Clase Online' not in df_fichas_temp.columns: df_fichas_temp['Valor Clase Online'] = ""
                        if 'Notas (Evaluaciones)' not in df_fichas_temp.columns: df_fichas_temp['Notas (Evaluaciones)'] = ""
                        if 'Billetera' not in df_fichas_temp.columns: df_fichas_temp['Billetera'] = 0.0
                        
                        if nombre_limpio.upper() not in df_fichas_temp['Estudiante'].astype(str).str.upper().values:
                            nueva_fila = pd.DataFrame({'Estudiante': [nombre_limpio], 'Teléfono': [""], 'Edad': [""], 'Nivel de Inglés': [""], 'Notas (Evaluaciones)': [""], 'Historial de Clases': [""], 'Valor Clase Presencial': [""], 'Dirección': [""], 'Valor Clase Online': [""], 'Billetera': [0.0]})
                            df_fichas_temp = pd.concat([df_fichas_temp, nueva_fila], ignore_index=True)
                            guardar_tabla("Estudiantes", df_fichas_temp)
                            st.success(f"✅ ¡{nombre_limpio} agregado al sistema!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("⚠️ Este estudiante ya existe.")
        
        lista_estudiantes = obtener_lista_estudiantes()
        if not lista_estudiantes: st.info("Agrega un estudiante primero.")
        else:
            estudiante_seleccionado = st.selectbox("🔍 Selecciona un estudiante:", ["-- Selecciona --"] + lista_estudiantes, key="selector_paciente_unico")
            if estudiante_seleccionado != "-- Selecciona --":
                df_fichas = cargar_tabla("Estudiantes")
                if df_fichas.empty or 'Estudiante' not in df_fichas.columns: 
                    df_fichas = pd.DataFrame(columns=['Estudiante', 'Teléfono', 'Edad', 'Nivel de Inglés', 'Notas (Evaluaciones)', 'Historial de Clases', 'Valor Clase Presencial', 'Dirección'])
                
                # Integrar columnas faltantes por si acaso
                for col in ['Valor Clase Presencial', 'Dirección', 'Valor Clase Online', 'Notas (Evaluaciones)']:
                    if col not in df_fichas.columns: df_fichas[col] = "" 
                if 'Billetera' not in df_fichas.columns: df_fichas['Billetera'] = 0.0
                
                if estudiante_seleccionado not in df_fichas['Estudiante'].values:
                    nueva_fila = pd.DataFrame({'Estudiante': [estudiante_seleccionado], 'Teléfono': [""], 'Edad': [""], 'Nivel de Inglés': [""], 'Notas (Evaluaciones)': [""], 'Historial de Clases': [""], 'Valor Clase Presencial': [""], 'Dirección': [""], 'Valor Clase Online': [""], 'Billetera': [0.0]})
                    df_fichas = pd.concat([df_fichas, nueva_fila], ignore_index=True)
                    guardar_tabla("Estudiantes", df_fichas)
                    
                idx_ficha = df_fichas.index[df_fichas['Estudiante'] == estudiante_seleccionado][0]
                tot_sesiones, tot_pagadas, tot_adeudadas = calcular_estadisticas_globales(estudiante_seleccionado)
                
                billetera_paciente = parse_dinero(df_fichas.at[idx_ficha, 'Billetera'])
                
                col_met1, col_met2, col_met3, col_met4 = st.columns(4)
                col_met1.metric("Clases Totales", tot_sesiones)
                col_met2.metric("Pagadas ✅", tot_pagadas)
                col_met3.metric("Adeudadas ❌", tot_adeudadas)
                col_met4.metric("💳 Billetera a Favor", f"${billetera_paciente:,.0f}".replace(",", "."))

                st.markdown("---")
                
                with st.form(key=f"form_ficha_{estudiante_seleccionado}"):
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        nuevo_tel = st.text_input("📞 Teléfono (Apoderado/Alumno):", value=str(df_fichas.at[idx_ficha, 'Teléfono']).replace('nan', ''))
                        nueva_edad = st.text_input("🎂 Edad / Curso:", value=str(df_fichas.at[idx_ficha, 'Edad']).replace('nan', ''))
                        nuevo_dir = st.text_input("📍 Dirección:", value=str(df_fichas.at[idx_ficha, 'Dirección']).replace('nan', ''), help="Se rellenará automáticamente en la agenda.")
                        nueva_billetera = st.text_input("💳 Billetera (Saldo a Favor):", value=str(df_fichas.at[idx_ficha, 'Billetera']).replace('nan', ''), help="Puedes editar esto manualmente si te transfieren dinero sin agendar.")
                    with col_f2:
                        nuevo_nivel = st.text_input("📈 Nivel de Inglés (Ej: A1, B2):", value=str(df_fichas.at[idx_ficha, 'Nivel de Inglés']).replace('nan', ''))
                        nuevo_valor = st.text_input("💰 Valor Clase Presencial (CLP):", value=str(df_fichas.at[idx_ficha, 'Valor Clase Presencial']).replace('nan', ''))
                        nuevo_valor_online = st.text_input("💻 Valor Clase Online (CLP):", value=str(df_fichas.at[idx_ficha, 'Valor Clase Online']).replace('nan', ''))
                        st.markdown("<br>", unsafe_allow_html=True) 

                    # NUEVO: Cuadro de Notas / Evaluaciones
                    st.markdown("#### 🎓 Calificaciones y Evaluaciones")
                    nuevas_notas_eval = st.text_area("Registra aquí los resultados de sus pruebas o quizzes:", value=str(df_fichas.at[idx_ficha, 'Notas (Evaluaciones)']).replace('nan', ''), height=100, help="Ejemplo: Prueba Unit 1: 6.5 | Quiz de Verbos: 85%")
                        
                    st.markdown("#### 📝 Desarrollo de Clases")
                    nota_hoy = st.text_area("➕ Agregar registro de clase de hoy:", value="", height=100, placeholder="Ej: Vimos Present Simple, dejé tarea del workbook pág. 12.")
                    nuevas_notas = st.text_area("✍️ Historial Académico Completo:", value=str(df_fichas.at[idx_ficha, 'Historial de Clases']).replace('nan', ''), height=200)
                    
                    if st.form_submit_button("💾 Guardar Expediente"):
                        df_fichas.at[idx_ficha, 'Teléfono'] = nuevo_tel
                        df_fichas.at[idx_ficha, 'Edad'] = nueva_edad
                        df_fichas.at[idx_ficha, 'Dirección'] = nuevo_dir
                        df_fichas.at[idx_ficha, 'Billetera'] = parse_dinero(nueva_billetera)
                        df_fichas.at[idx_ficha, 'Nivel de Inglés'] = nuevo_nivel
                        df_fichas.at[idx_ficha, 'Notas (Evaluaciones)'] = nuevas_notas_eval
                        
                        texto_final = nuevas_notas
                        if nota_hoy.strip() != "":
                            fecha_actual = date.today().strftime("%d/%m/%Y")
                            if texto_final.strip() != "":
                                texto_final = f"{texto_final.strip()}\n\n📅 [{fecha_actual}] - {nota_hoy.strip()}"
                            else:
                                texto_final = f"📅 [{fecha_actual}] - {nota_hoy.strip()}"
                                
                        df_fichas.at[idx_ficha, 'Historial de Clases'] = texto_final
                        df_fichas.at[idx_ficha, 'Valor Clase Presencial'] = nuevo_valor
                        df_fichas.at[idx_ficha, 'Valor Clase Online'] = nuevo_valor_online
                        guardar_tabla("Estudiantes", df_fichas)
                        st.success("¡Expediente actualizado!")
                        time.sleep(1)
                        st.rerun()

    with tab4:
        st.header("📊 Finanzas y Pagos")
        
        meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        año_actual = date.today().year
        
        st.markdown("### 📅 Seleccionar Periodo")
        col_m, col_a = st.columns(2)
        with col_m:
            mes_seleccionado = st.selectbox("Mes:", meses_nombres, index=st.session_state.app_fecha_sel.month - 1)
        with col_a:
            año_seleccionado = st.selectbox("Año:", [año_actual - 1, año_actual, año_actual + 1, año_actual + 2], index=1)
            
        mes_num = meses_nombres.index(mes_seleccionado) + 1
        mes_dashboard = date(año_seleccionado, mes_num, 1)
        
        stats = calcular_dashboard_mensual(mes_dashboard)
        
        # Calcular Billeteras Activas Globales
        df_fichas_billetera = cargar_tabla("Estudiantes")
        if not df_fichas_billetera.empty and 'Billetera' in df_fichas_billetera.columns:
            total_billetera_global = pd.to_numeric(df_fichas_billetera['Billetera'], errors='coerce').fillna(0).sum()
        else:
            total_billetera_global = 0.0
        
        st.markdown(f"### 📊 Resultados de {mes_seleccionado} {año_seleccionado}")
        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        col_d1.metric("Clases impartidas", stats["total_sesiones"])
        col_d2.metric("💰 Ingresos Mes", f"${stats['ingresos']:,.0f}".replace(",", "."))
        col_d3.metric("⏳ Deuda Pendiente", f"${stats['por_cobrar']:,.0f}".replace(",", "."))
        col_d4.metric("💳 Billeteras a Favor", f"${total_billetera_global:,.0f}".replace(",", "."), help="Dinero adelantado por estudiantes aún no consumido")
        
        st.markdown("---")
        
        st.markdown("#### 🔍 Desglose de Contabilidad")
        col_des1, col_des2 = st.columns(2)
        with col_des1:
            st.success(f"**Ingresos Clases Presenciales:** ${stats['ingresos_sesiones']:,.0f}".replace(",", "."))
            st.success(f"**Ingresos Clases Online:** ${stats['ingresos_pautas']:,.0f}".replace(",", "."))
        with col_des2:
            st.warning(f"**Deuda Clases Presenciales:** ${stats['deuda_sesiones']:,.0f}".replace(",", "."))
            st.warning(f"**Deuda Clases Online:** ${stats['deuda_pautas']:,.0f}".replace(",", "."))

        st.markdown("---")
        
        st.markdown(f"### 📋 Detalle de Clases - {mes_seleccionado} {año_seleccionado}")
        df_completo_dash = cargar_tabla("Clases")
        if not df_completo_dash.empty and 'Fecha' in df_completo_dash.columns:
            prefijo_mes_sel = mes_dashboard.strftime("%Y-%m")
            df_mes_det = df_completo_dash[df_completo_dash['Fecha'].astype(str).str.startswith(prefijo_mes_sel)].copy()
            df_mes_det = df_mes_det[~df_mes_det['Modalidad / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"])]
            df_mes_det = df_mes_det[(df_mes_det['Estudiante'].astype(str).str.strip() != "") & (df_mes_det['Estudiante'].astype(str).str.strip().str.upper() != "ALMUERZO")]
            
            if not df_mes_det.empty:
                mapa_val_dash = obtener_valor_por_estudiante()
                mapa_pau_dash = obtener_valor_online_por_estudiante()
                df_mes_det['Estudiante_norm'] = df_mes_det['Estudiante'].astype(str).str.strip().str.upper()
                
                df_mes_det['Hora'] = df_mes_det['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip()
                if 'Abono ($)' not in df_mes_det.columns: df_mes_det['Abono ($)'] = ""
                
                def asignar_valor_str(row):
                    if str(row['Modalidad / Motivo']).strip() == "Clase Online 💻":
                        val = mapa_pau_dash.get(row['Estudiante_norm'], 0.0)
                    else:
                        val = mapa_val_dash.get(row['Estudiante_norm'], 0.0)
                    return f"${val:,.0f}".replace(",", ".")
                
                df_mes_det['Costo Sesión'] = df_mes_det.apply(asignar_valor_str, axis=1)
                
                df_mostrar_dash = df_mes_det[['Fecha', 'Hora', 'Estudiante', 'Modalidad / Motivo', 'Costo Sesión', 'Pago', 'Abono ($)']].sort_values(by=['Fecha', 'Hora'])
                
                st.markdown("💡 *Si editas el Pago o Abono aquí, se recalculará automáticamente tu contabilidad al guardar.*")
                
                df_editado_dash = st.data_editor(
                    df_mostrar_dash,
                    use_container_width=True,
                    hide_index=True,
                    key=f"editor_dash_{mes_seleccionado}_{año_seleccionado}",
                    column_config={
                        "Fecha": st.column_config.TextColumn("Fecha", disabled=True),
                        "Hora": st.column_config.TextColumn("Hora", disabled=True),
                        "Estudiante": st.column_config.TextColumn("Estudiante", disabled=True),
                        "Modalidad / Motivo": st.column_config.TextColumn("Modalidad", disabled=True),
                        "Costo Sesión": st.column_config.TextColumn("Valor Base ($)", disabled=True), 
                        "Pago": st.column_config.SelectboxColumn("Pago", options=["No pagada ❌", "Pagada ✅", "Abono Parcial ⏳", "Descontar Billetera 💳", "Pagada con Billetera ✅", "Pagada (Excedente) ✅", "-"]),
                        "Abono ($)": st.column_config.TextColumn("Abono Efectivo ($)")
                    }
                )
                
                if st.button("💾 Guardar Cambios del Mes", type="primary", use_container_width=True):
                    with st.spinner("Guardando pagos..."):
                        df_full_clases_dash = cargar_tabla("Clases")
                        if 'Abono ($)' not in df_full_clases_dash.columns: df_full_clases_dash['Abono ($)'] = ""
                        
                        for index, row in df_editado_dash.iterrows():
                            hora_limpia = str(row['Hora']).replace("🔴 ", "").replace("🔴", "").strip()
                            mask_clinica = (df_full_clases_dash['Fecha'] == row['Fecha']) & \
                                           (df_full_clases_dash['Hora'].astype(str).str.replace("🔴 ", "").str.replace("🔴", "").str.strip() == hora_limpia) & \
                                           (df_full_clases_dash['Estudiante'].astype(str).str.strip().str.upper() == str(row['Estudiante']).strip().upper())
                                           
                            if not df_full_clases_dash[mask_clinica].empty:
                                idx_clin = df_full_clases_dash[mask_clinica].index[0]
                                df_full_clases_dash.at[idx_clin, 'Pago'] = row['Pago']
                                df_full_clases_dash.at[idx_clin, 'Abono ($)'] = row['Abono ($)']

                        guardar_tabla("Clases", df_full_clases_dash)
                        st.success("✅ ¡Cambios guardados con éxito! Los números de arriba ya están actualizados.")
                        time.sleep(1.5)
                        st.rerun()
            else:
                st.info(f"No hay clases registradas para {mes_seleccionado} {año_seleccionado}.")
        else:
            st.info("No hay datos en la agenda aún.")

        st.markdown("---")
        
        st.markdown(f"### 📈 Resumen Anual {año_seleccionado}")
        
        datos_anuales = []
        for m in range(1, 13):
            stats_m = calcular_dashboard_mensual(date(año_seleccionado, m, 1))
            if stats_m["total_sesiones"] > 0 or stats_m["ingresos"] > 0 or stats_m["por_cobrar"] > 0:
                datos_anuales.append({
                    "Mes": meses_nombres[m-1],
                    "Clases Dadas": stats_m["total_sesiones"],
                    "Ingresos Pagados": stats_m['ingresos'],
                    "Deuda Pendiente": stats_m['por_cobrar'],
                    "Total Mensual": stats_m['ingresos'] + stats_m['por_cobrar']
                })
        
        if datos_anuales:
            df_anual = pd.DataFrame(datos_anuales)
            df_anual_visual = df_anual.copy()
            for col in ["Ingresos Pagados", "Deuda Pendiente", "Total Mensual"]:
                df_anual_visual[col] = df_anual_visual[col].apply(lambda x: f"${x:,.0f}".replace(",", "."))
            st.dataframe(df_anual_visual, use_container_width=True, hide_index=True)
        else:
            st.info(f"No hay movimientos financieros registrados en el sistema durante {año_seleccionado}.")

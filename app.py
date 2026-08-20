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

# --- ESTILOS PERSONALIZADOS AVANZADOS (UI/UX CELULAR Y PC) ---
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .titulo-principal { color: #2C3E50; text-align: center; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 800; font-size: 2.5rem; margin-bottom: -10px; }
    .subtitulo { color: #18BC9C; text-align: center; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-weight: 600; font-size: 1.2rem; margin-bottom: 2rem; }
    
    /* Diseño base de los botones del calendario (GLOBAL) */
    div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) button {
        width: 100% !important; padding: 12px 0px !important; border-radius: 8px !important;
        font-size: 1rem !important; font-weight: 700 !important; box-shadow: 0px 1px 3px rgba(0,0,0,0.1) !important;
        border: 1px solid #E0E6ED !important; min-height: 45px !important;
    }

    /* 📱 MAGIA EXCLUSIVA PARA CELULARES (Se desactiva en el PC) */
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"]:has(> div:nth-child(7)) {
            display: grid !important;
            grid-template-columns: repeat(7, 1fr) !important;
            gap: 4px !important;
            width: 100% !important;
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

st.markdown('<p class="titulo-principal">Centro de Comando</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitulo">Kinesiología CGM — Orden y Planificación</p>', unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_bd():
    credenciales_json = json.loads(st.secrets["gcp_credentials"], strict=False)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(credenciales_json, scopes=scopes)
    cliente = gspread.authorize(creds)
    return cliente.open("Base_Datos_Kine")

try: doc = conectar_bd()
except Exception as e:
    st.error(f"Error conectando a la base de datos: {e}")
    st.stop()

def obtener_hoja(nombre):
    try: return doc.worksheet(nombre)
    except gspread.exceptions.WorksheetNotFound: return doc.add_worksheet(title=nombre, rows="1000", cols="20")

# 🛡️ SISTEMA ANTI-FANTASMAS (Evita cargar tablas vacías por error de Google)
@st.cache_data(ttl=60)
def cargar_tabla(nombre_hoja):
    try:
        hoja = obtener_hoja(nombre_hoja)
        datos = hoja.get_all_records()
        return pd.DataFrame(datos) if datos else pd.DataFrame()
    except Exception as e:
        st.cache_data.clear() 
        st.error(f"⚠️ Google Sheets bloqueó la lectura por un segundo. Por seguridad, la app se pausó para no mostrarte datos vacíos. Presiona la tecla 'F5' o recarga la página de tu navegador.")
        st.stop() 

def guardar_tabla(nombre_hoja, df):
    hoja = obtener_hoja(nombre_hoja)
    hoja.clear()
    if not df.empty:
        # BLINDAJE CONTRA JSON SERIALIZABLE ERROR: Todo a string nativo
        df_limpio = df.fillna("").astype(str)
        hoja.update([df_limpio.columns.values.tolist()] + df_limpio.values.tolist())
    st.cache_data.clear()

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
        cols_dias[i].markdown(f"<div class='dia-semana' style='text-align:center; font-weight:700; color:#18BC9C; padding-bottom: 5px;'>{d}</div>", unsafe_allow_html=True)

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

    def guardar_dia(tipo, fecha, df_dia):
        df_guardar = df_dia.copy()
        df_guardar.insert(0, 'Fecha', fecha)
        try:
            hoja_segura = obtener_hoja(tipo)
            datos_seguros = hoja_segura.get_all_records()
            df_completo = pd.DataFrame(datos_seguros) if datos_seguros else pd.DataFrame()
        except Exception as e:
            st.error(f"🚨 SEGURIDAD ACTIVADA: Google rechazó la conexión. Intenta de nuevo en 1 minuto.")
            return False 
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_completo = df_completo[df_completo['Fecha'] != fecha]
            df_final = pd.concat([df_completo, df_guardar], ignore_index=True)
        else:
            df_final = df_guardar
        guardar_tabla(tipo, df_final)
        return True 

    # --- RESTO DE FUNCIONES ---
    def cargar_datos_clinica(fecha):
        df_completo = cargar_tabla("Clinica")
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_dia = df_completo[df_completo['Fecha'] == fecha]
            if not df_dia.empty: return df_dia.drop(columns=['Fecha']).reset_index(drop=True)
        return pd.DataFrame({
            "Hora": horas_30_min, "Paciente": [""] * len(horas_30_min), "Detalle / Motivo": [""] * len(horas_30_min),
            "Dirección": [""] * len(horas_30_min), "Minutos de Viaje": [0] * len(horas_30_min), 
            "Hora de Salida": [""] * len(horas_30_min), "Ruta Maps": [""] * len(horas_30_min), "Alarma": [""] * len(horas_30_min),
            "Estado": ["Libre 🟢"] * len(horas_30_min), "N° Sesión": [""] * len(horas_30_min), "Pago": ["-"] * len(horas_30_min),
            "Recordatorio": [""] * len(horas_30_min)
        })

    def cargar_datos_personal(fecha):
        df_completo = cargar_tabla("Personal")
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_dia = df_completo[df_completo['Fecha'] == fecha]
            if not df_dia.empty: return df_dia.drop(columns=['Fecha']).reset_index(drop=True)
        return pd.DataFrame({"Hora": horas_30_min, "Actividad": [""] * len(horas_30_min), "Categoría": ["-"] * len(horas_30_min), "Notas": [""] * len(horas_30_min)})

    def obtener_actividad_por_hora(df_personal):
        if df_personal.empty or 'Hora' not in df_personal.columns: return {}
        return dict(zip(df_personal['Hora'].astype(str).str.strip(), df_personal['Actividad'].astype(str).str.strip()))

    def calcular_tiempo_gps(origen_coords_o_texto, destino):
        try:
            geolocator = Nominatim(user_agent="sustancia_x_agenda", timeout=5)
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
        df_completo = cargar_tabla("Clinica")
        if df_completo.empty or 'Paciente' not in df_completo.columns: return []
        pacientes = set()
        for p in df_completo['Paciente'].dropna().unique():
            p_str = str(p).strip()
            if p_str != "" and p_str.upper() != "ALMUERZO": pacientes.add(p_str.title()) 
        return sorted(list(pacientes))

    def calcular_estadisticas_globales(nombre_paciente):
        nombre_norm = str(nombre_paciente).strip().upper()
        df_completo = cargar_tabla("Clinica")
        if df_completo.empty or 'Paciente' not in df_completo.columns: return 0, 0, 0
        df_pac = df_completo[(df_completo['Paciente'].str.strip().str.upper() == nombre_norm) & (~df_completo['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))]
        tot_sesiones = len(df_pac)
        pagadas = len(df_pac[df_pac['Pago'] == "Pagada ✅"])
        adeudadas = len(df_pac[df_pac['Pago'] == "No pagada ❌"])
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
            try: mapa[nombre] = float(str(valor).replace(".", "").replace(",", "").strip())
            except (ValueError, TypeError): mapa[nombre] = 0.0
        return mapa

    def construir_link_whatsapp(telefono, nombre_paciente, fecha_visual_str, hora_str):
        if not telefono or str(telefono).strip() == "": return ""
        solo_digitos = "".join(ch for ch in str(telefono) if ch.isdigit())
        if solo_digitos == "": return ""
        if not solo_digitos.startswith("56"): solo_digitos = "56" + solo_digitos.lstrip("0")
        mensaje = f"Hola {nombre_paciente.title()}! Te confirmo tu sesión de kinesiología el {fecha_visual_str} a las {hora_str} hrs. Cualquier cosa avísame 🙂"
        texto_codificado = urllib.parse.quote(mensaje)
        return f"https://wa.me/{solo_digitos}?text={texto_codificado}"

    def calcular_dashboard_mensual(fecha_referencia):
        df_completo = cargar_tabla("Clinica")
        resultado = {"total_sesiones": 0, "pagadas": 0, "adeudadas": 0, "ingresos": 0.0, "por_cobrar": 0.0, "pacientes_con_deuda": 0, "pacientes_totales": 0}
        if df_completo.empty or 'Fecha' not in df_completo.columns: return resultado
        prefijo_mes = fecha_referencia.strftime("%Y-%m")
        df_mes = df_completo[df_completo['Fecha'].astype(str).str.startswith(prefijo_mes)].copy()
        df_mes = df_mes[~df_mes['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"])]
        df_mes = df_mes[(df_mes['Paciente'].astype(str).str.strip() != "") & (df_mes['Paciente'].astype(str).str.strip().str.upper() != "ALMUERZO")]
        if df_mes.empty: return resultado
        mapa_valores = obtener_valor_por_paciente()
        df_mes['Paciente_norm'] = df_mes['Paciente'].astype(str).str.strip().str.upper()
        df_mes['Valor'] = df_mes['Paciente_norm'].map(mapa_valores).fillna(0.0)
        resultado["total_sesiones"] = len(df_mes)
        resultado["pagadas"] = len(df_mes[df_mes['Pago'] == "Pagada ✅"])
        resultado["adeudadas"] = len(df_mes[df_mes['Pago'] == "No pagada ❌"])
        resultado["ingresos"] = df_mes[df_mes['Pago'] == "Pagada ✅"]['Valor'].sum()
        resultado["por_cobrar"] = df_mes[df_mes['Pago'] == "No pagada ❌"]['Valor'].sum()
        pacientes_totales = df_mes['Paciente_norm'].unique()
        pacientes_deuda = df_mes[df_mes['Pago'] == "No pagada ❌"]['Paciente_norm'].unique()
        resultado["pacientes_totales"] = len(pacientes_totales)
        resultado["pacientes_con_deuda"] = len(pacientes_deuda)
        return resultado

    def calcular_sesion_historica(nombre_paciente, fecha_actual, hora_actual):
        if nombre_paciente == "": return ""
        nombre_norm = str(nombre_paciente).strip().upper()
        df_completo = cargar_tabla("Clinica")
        if df_completo.empty or 'Paciente' not in df_completo.columns: return "1"
        df_hist = df_completo[(df_completo['Paciente'].str.strip().str.upper() == nombre_norm) & (~df_completo['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))].copy()
        if df_hist.empty: return "1"
        df_hist['FechaHora'] = pd.to_datetime(df_hist['Fecha'] + ' ' + df_hist['Hora'])
        fecha_hora_actual = pd.to_datetime(f"{fecha_actual} {hora_actual}")
        contador = len(df_hist[df_hist['FechaHora'] <= fecha_hora_actual])
        return str(contador if contador > 0 else 1)

    # --- CARGA Y PROTECCIÓN DE DATOS DEL DÍA ---
    df_clinica = cargar_datos_clinica(fecha_str)
    df_personal = cargar_datos_personal(fecha_str)

    df_clinica['Paciente'] = df_clinica['Paciente'].fillna("") 
    df_clinica['Dirección'] = df_clinica['Dirección'].fillna("").astype(str)
    df_clinica['Minutos de Viaje'] = pd.to_numeric(df_clinica['Minutos de Viaje'], errors='coerce').fillna(0).astype(int)
    df_clinica['Hora de Salida'] = df_clinica['Hora de Salida'].fillna("").astype(str)
    df_clinica['Ruta Maps'] = df_clinica['Ruta Maps'].fillna("").astype(str)
    if 'Alarma' not in df_clinica.columns: df_clinica['Alarma'] = ""
    df_clinica['Alarma'] = df_clinica['Alarma'].fillna("").astype(str)
    df_clinica['N° Sesión'] = df_clinica['N° Sesión'].fillna("").astype(str)
    df_clinica['Pago'] = df_clinica['Pago'].fillna("-").astype(str)
    if 'Recordatorio' not in df_clinica.columns: df_clinica['Recordatorio'] = ""
    df_clinica['Recordatorio'] = df_clinica['Recordatorio'].fillna("").astype(str)

    df_personal['Actividad'] = df_personal['Actividad'].fillna("").astype(str)
    df_personal['Categoría'] = df_personal['Categoría'].fillna("-").astype(str)
    df_personal['Notas'] = df_personal['Notas'].fillna("").astype(str)

    for index in df_clinica.index:
        pac_clinica = str(df_clinica.at[index, 'Paciente']).strip()
        act_personal = str(df_personal.at[index, 'Actividad']).strip()
        if pac_clinica != "" and pac_clinica.upper() != "ALMUERZO":
            if not act_personal.startswith("🩺 Atendiendo"):
                df_personal.at[index, 'Actividad'] = f"🩺 Atendiendo: {pac_clinica}"
                df_personal.at[index, 'Categoría'] = "Clínica"
        else:
            if act_personal.startswith("🩺 Atendiendo"):
                df_personal.at[index, 'Actividad'] = ""
                df_personal.at[index, 'Categoría'] = "-"

    mapa_personal = obtener_actividad_por_hora(df_personal) 
    mapa_telefonos = obtener_telefono_por_paciente()
    mapa_direcciones = obtener_direccion_por_paciente()

    for index in df_clinica.index:
        paciente = str(df_clinica.at[index, 'Paciente']).strip()
        direccion = str(df_clinica.at[index, 'Dirección']).strip()
        hora_str = str(df_clinica.at[index, 'Hora']).strip()
        minutos = int(df_clinica.at[index, 'Minutos de Viaje'])
        pago_actual = str(df_clinica.at[index, 'Pago']).strip()
        sesion_actual = str(df_clinica.at[index, 'N° Sesión']).strip()
        detalle_actual = str(df_clinica.at[index, 'Detalle / Motivo']).strip()
        actividad_personal = mapa_personal.get(hora_str, "") 
        es_tramite = (detalle_actual == "Personal / Trámite 🛑")
        es_gimnasio = (detalle_actual == "Gimnasio 🏋️")
        es_cita_clinica = (detalle_actual in ["Rehabilitación", "Entrenamiento", "Preventivo"])
        es_almuerzo = (paciente.upper() == "ALMUERZO")
        hay_paciente = (paciente != "" and not es_almuerzo)
        
        if hay_paciente and direccion == "":
            dir_guardada = mapa_direcciones.get(paciente.upper(), "")
            if dir_guardada != "":
                direccion = dir_guardada
                df_clinica.at[index, 'Dirección'] = direccion

        if hay_paciente or es_tramite or es_gimnasio or es_cita_clinica:
            if direccion != "":
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
                df_clinica.at[index, 'N° Sesión'] = "-"
            else:
                if pago_actual == "-" or pago_actual == "": df_clinica.at[index, 'Pago'] = "No pagada ❌"
                es_numero_auto = False
                if sesion_actual == "" or sesion_actual == "-": es_numero_auto = True
                else:
                    try: float(sesion_actual); es_numero_auto = True
                    except ValueError: es_numero_auto = False
                if es_numero_auto: df_clinica.at[index, 'N° Sesión'] = calcular_sesion_historica(paciente, fecha_str, hora_str)
            if hay_paciente:
                telefono_paciente = mapa_telefonos.get(paciente.strip().upper(), "")
                df_clinica.at[index, 'Recordatorio'] = construir_link_whatsapp(telefono_paciente, paciente, fecha_visual, hora_str)
            else: df_clinica.at[index, 'Recordatorio'] = ""
        else:
            df_clinica.at[index, 'Ruta Maps'] = ""; df_clinica.at[index, 'Hora de Salida'] = ""; df_clinica.at[index, 'Alarma'] = ""
            df_clinica.at[index, 'N° Sesión'] = ""; df_clinica.at[index, 'Pago'] = "-"; df_clinica.at[index, 'Recordatorio'] = ""

        if actividad_personal != "" and (hay_paciente or es_cita_clinica):
            if actividad_personal.startswith("🩺 Atendiendo"): df_clinica.at[index, 'Estado'] = "Agendado 🔒"
            else: df_clinica.at[index, 'Estado'] = "⚠️ TOPE HORARIO ⚠️"
        elif actividad_personal != "": df_clinica.at[index, 'Estado'] = f"Bloqueado ({actividad_personal}) 🛑"
        elif es_tramite: df_clinica.at[index, 'Estado'] = "Bloqueado 🛑"
        elif es_gimnasio: df_clinica.at[index, 'Estado'] = "Gimnasio 🏋️"
        elif es_cita_clinica or hay_paciente: df_clinica.at[index, 'Estado'] = "Agendado 🔒"
        elif es_almuerzo: df_clinica.at[index, 'Estado'] = "-"
        else:
            if index > 0:
                paciente_ant = str(df_clinica.at[index - 1, 'Paciente']).strip()
                detalle_ant = str(df_clinica.at[index - 1, 'Detalle / Motivo']).strip()
                if (detalle_ant == "Personal / Trámite 🛑") or (detalle_ant == "Gimnasio 🏋️"):
                    df_clinica.at[index, 'Estado'] = f"Bloqueado ({paciente_ant if paciente_ant != '' else ('Trámite' if detalle_ant == 'Personal / Trámite 🛑' else 'Gimnasio')}) ⏳"
                    continue
                elif (detalle_ant in ["Rehabilitación", "Entrenamiento", "Preventivo"]) or (paciente_ant != "" and paciente_ant.upper() != "ALMUERZO"):
                    df_clinica.at[index, 'Estado'] = f"En sesión ({paciente_ant if paciente_ant != '' else 'Paciente'}) ⏳"
                    continue
            df_clinica.at[index, 'Estado'] = "Libre 🟢"

    # --- PESTAÑAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["🩺 Calendario", "🕰️ Horario Personal", "📁 Fichas Clínicas", "📊 Dashboard"])

    with tab1:
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1: st.header(f"📅 Agenda Clínica - {fecha_visual}")
        with col_t2:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            btn_guardar_clinica = st.button("💾 Guardar Cambios", use_container_width=True, type="primary", key="btn_save_clinica")
        
        with st.expander("⚡ Agendar Existente / Paquetes / Reagendar"):
            tab_ex, tab_ag, tab_re = st.tabs(["➕ Un Paciente Existente", "🔄 Múltiples Sesiones", "✂️ Reagendar Cita"])
            
            with tab_ex:
                lista_pacs = obtener_lista_pacientes()
                if not lista_pacs:
                    st.info("Primero agrega un paciente manualmente en la tabla inferior.")
                else:
                    col_e1, col_e2, col_e3 = st.columns(3)
                    with col_e1:
                        pac_ex = st.selectbox("1. Paciente Existente:", ["-- Selecciona --"] + lista_pacs)
                        mot_ex = st.selectbox("Motivo de sesión:", ["Rehabilitación", "Entrenamiento", "Preventivo"], key="mot_ex")
                    with col_e2:
                        hora_ex = st.selectbox(f"2. Hora (para este día):", horas_30_min, key="hora_ex")
                    with col_e3:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        btn_ex = st.button("🚀 Agendar en esta hora", use_container_width=True)
                    if btn_ex:
                        if pac_ex == "-- Selecciona --": st.error("Por favor selecciona un paciente.")
                        else:
                            idx_ex = df_clinica.index[df_clinica['Hora'] == hora_ex].tolist()[0]
                            if str(df_clinica.at[idx_ex, 'Paciente']).strip() != "": st.error("⚠️ Esta hora ya está ocupada.")
                            else:
                                with st.spinner("Agendando..."):
                                    df_clinica.at[idx_ex, 'Paciente'] = pac_ex
                                    df_clinica.at[idx_ex, 'Detalle / Motivo'] = mot_ex
                                    df_clinica.at[idx_ex, 'Dirección'] = mapa_direcciones.get(pac_ex.upper(), "")
                                    df_clinica.at[idx_ex, 'Minutos de Viaje'] = 0
                                    df_clinica.at[idx_ex, 'Pago'] = "No pagada ❌"
                                    df_clinica.at[idx_ex, 'N° Sesión'] = ""
                                    guardar_dia("Clinica", fecha_str, df_clinica)
                                    st.success(f"✅ ¡{pac_ex} agendado a las {hora_ex}!")
                                    time.sleep(1)
                                    st.rerun()

            with tab_ag:
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    m_paciente = st.text_input("Paciente:")
                    m_motivo = st.selectbox("Motivo:", ["Rehabilitación", "Entrenamiento", "Preventivo"])
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
                                    idx_hora = df_dia_futuro.index[df_dia_futuro['Hora'] == m_hora].tolist()
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
                                            df_dia_futuro.at[idx, 'N° Sesión'] = "" 
                                            exito_agendar = guardar_dia("Clinica", f_str, df_dia_futuro)
                                            if exito_agendar:
                                                fechas_exitosas.append(fecha_iter.strftime("%d/%m/%Y"))
                                                sesiones_logradas += 1
                                                time.sleep(0.3)
                                        else: fechas_ocupadas.append(fecha_iter.strftime("%d/%m/%Y"))
                                fecha_iter += timedelta(days=1)
                                dias_buscados += 1
                        if sesiones_logradas == m_sesiones: st.success("✅ ¡Agendado!")
                        else: st.warning(f"⚠️ Solo se agendaron {sesiones_logradas}.")
                        st.rerun()

            with tab_re:
                sesiones_activas = df_clinica[(df_clinica['Paciente'].str.strip() != "") & (df_clinica['Paciente'].str.upper() != "ALMUERZO")]
                opciones_citas = ["-- Selecciona --"] + [f"{r['Hora']} - {r['Paciente']}" for i, r in sesiones_activas.iterrows()]
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
                    hora_origen = cita_origen.split(" - ")[0]
                    fila_origen = df_clinica[df_clinica['Hora'] == hora_origen].iloc[0]
                    f_dest_str = fecha_destino.strftime("%Y-%m-%d")
                    df_clinica_dest = cargar_datos_clinica(f_dest_str)
                    idx_dest = df_clinica_dest.index[df_clinica_dest['Hora'] == hora_destino].tolist()[0]
                    if str(df_clinica_dest.at[idx_dest, 'Paciente']).strip() != "":
                        st.error("⚠️ La hora de destino está ocupada.")
                    else:
                        with st.spinner("Procesando..."):
                            df_clinica_dest.at[idx_dest, 'Paciente'] = str(fila_origen['Paciente'])
                            df_clinica_dest.at[idx_dest, 'Detalle / Motivo'] = str(fila_origen['Detalle / Motivo'])
                            df_clinica_dest.at[idx_dest, 'Dirección'] = str(fila_origen['Dirección'])
                            df_clinica_dest.at[idx_dest, 'Minutos de Viaje'] = int(fila_origen['Minutos de Viaje'])
                            df_clinica_dest.at[idx_dest, 'Pago'] = "No pagada ❌"
                            df_clinica_dest.at[idx_dest, 'N° Sesión'] = "" 
                            exito_r = guardar_dia("Clinica", f_dest_str, df_clinica_dest)
                            if exito_r and accion_reagendar == "Mover":
                                idx_origen = df_clinica.index[df_clinica['Hora'] == hora_origen].tolist()[0]
                                df_clinica.at[idx_origen, 'Paciente'] = ""
                                df_clinica.at[idx_origen, 'Detalle / Motivo'] = "-"
                                df_clinica.at[idx_origen, 'Dirección'] = ""
                                df_clinica.at[idx_origen, 'Minutos de Viaje'] = 0
                                df_clinica.at[idx_origen, 'Pago'] = "-"
                                df_clinica.at[idx_origen, 'N° Sesión'] = ""
                                guardar_dia("Clinica", fecha_str, df_clinica)
                            if exito_r:
                                st.success("✅ ¡Listo!")
                                time.sleep(1)
                                st.rerun()

        # --- BUSCADOR CON TELETRANSPORTADOR ---
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
                            
                            st.markdown("🎯 **Ir directamente al día para editar (Ej: Marcar como Pagada):**")
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
                                    else:
                                        st.error("Selecciona una cita válida de la lista.")
                        else: st.warning("No se encontraron sesiones.")

        with st.expander("📍 Viajes y Alarmas"):
            st.markdown("⚠️ *El botón automático usa mapas gratuitos que a veces no encuentran las calles. Lo mejor es que tú escribas los minutos a mano en la tabla y presiones 'Guardar Cambios'.*")
            ubicacion_gps = streamlit_geolocation()
            direccion_base = st.text_input("O escribe tu base:", value="Gomez Carreño, Viña del Mar")
            if st.button("⚡ Calcular Tiempos Automáticos de Hoy"):
                with st.spinner("Calculando..."):
                    origen_final = direccion_base
                    fallos = 0
                    if ubicacion_gps and ubicacion_gps.get('latitude') is not None: origen_final = (ubicacion_gps['latitude'], ubicacion_gps['longitude'])
                    for idx in df_clinica.index:
                        dir_paciente, hora_paciente = str(df_clinica.at[idx, 'Dirección']).strip(), str(df_clinica.at[idx, 'Hora']).strip()
                        if dir_paciente != "":
                            minutos_gps = calcular_tiempo_gps(origen_final, dir_paciente)
                            if minutos_gps > 0: df_clinica.at[idx, 'Minutos de Viaje'] = minutos_gps
                            else: fallos += 1
                    exito = guardar_dia("Clinica", fecha_str, df_clinica)
                    if exito: 
                        if fallos > 0: st.warning(f"Se calculó, pero el mapa falló en {fallos} dirección(es). Pon los minutos manualmente.")
                        else: st.success("¡Calculado!")
                    st.rerun()

        st.caption("💡 Tip: Presiona 'Enter' luego de escribir en una celda para no perder los datos al guardar.")
        df_clinica_editado = st.data_editor(
            df_clinica, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"editor_clinica_{fecha_str}",
            column_order=("Hora", "Paciente", "Detalle / Motivo", "Dirección", "Minutos de Viaje", "Hora de Salida", "Ruta Maps", "Alarma", "Recordatorio", "Estado", "N° Sesión", "Pago"),
            column_config={
                "Detalle / Motivo": st.column_config.SelectboxColumn("Motivo", options=["Rehabilitación", "Entrenamiento", "Preventivo", "Personal / Trámite 🛑", "Gimnasio 🏋️", "-"]),
                "Dirección": st.column_config.TextColumn("Dirección"),
                "Minutos de Viaje": st.column_config.NumberColumn("Min. Viaje", min_value=0, step=1),
                "Hora de Salida": st.column_config.TextColumn("Salida", disabled=True),
                "Ruta Maps": st.column_config.LinkColumn("🗺️ Mapa", disabled=True, display_text="Ver Mapa"),
                "Alarma": st.column_config.LinkColumn("🔔 Alarma", disabled=True, display_text="Crear Alarma"),
                "Recordatorio": st.column_config.LinkColumn("📲 WhatsApp", disabled=True, display_text="Enviar"),
                "Estado": st.column_config.TextColumn("Estado", disabled=True),
                "N° Sesión": st.column_config.TextColumn("Sesión", help="Calculado auto."),
                "Pago": st.column_config.SelectboxColumn("Pago", options=["No pagada ❌", "Pagada ✅", "-"])
            }
        )
        if btn_guardar_clinica:
            exito1 = guardar_dia("Clinica", fecha_str, df_clinica_editado)
            exito2 = guardar_dia("Personal", fecha_str, df_personal)
            if exito1 and exito2:
                st.success("¡Agenda guardada!")
                st.rerun()

    with tab2:
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1: st.header(f"🕰️ Horario Personal - {fecha_visual}")
        with col_p2:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            btn_guardar_personal = st.button("💾 Guardar Personal", use_container_width=True, type="primary", key="btn_save_personal")
            
        # --- NUEVA FUNCIÓN: BLOQUEO RÁPIDO DE HORAS ---
        with st.expander("⏳ Bloqueo Rápido de Tiempo (60 min o más)"):
            st.markdown("Usa esta herramienta para bloquear varias horas seguidas en un par de clics.")
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
                if act_b.strip() == "":
                    st.error("Escribe el nombre de la actividad.")
                else:
                    slots_necesarios = int(duracion_b.split(" ")[0]) // 30
                    idx_inicio = df_personal.index[df_personal['Hora'] == hora_inicio_b].tolist()[0]
                    idx_fin = min(idx_inicio + slots_necesarios, len(df_personal))
                    
                    with st.spinner("Bloqueando..."):
                        for i in range(idx_inicio, idx_fin):
                            # Solo bloquea si no hay un paciente atendiendo
                            if not str(df_personal.at[i, 'Actividad']).startswith("🩺 Atendiendo"):
                                df_personal.at[i, 'Actividad'] = act_b
                                df_personal.at[i, 'Categoría'] = cat_b
                        guardar_dia("Personal", fecha_str, df_personal)
                        st.success(f"✅ ¡Bloqueo de {duracion_b} aplicado!")
                        time.sleep(1)
                        st.rerun()

        df_personal_editado = st.data_editor(
            df_personal, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"editor_personal_{fecha_str}",
            column_order=("Hora", "Actividad", "Categoría", "Notas"),
            column_config={
                "Hora": st.column_config.TextColumn("Hora", disabled=True),
                "Actividad": st.column_config.TextColumn("Actividad"),
                "Categoría": st.column_config.SelectboxColumn("Categoría", options=["Tesis Magíster", "Proyecto Sustancia X", "Mascota", "Salud", "Ocio", "Trámites", "Clínica", "General", "-"]),
            }
        )
        if btn_guardar_personal:
            exito = guardar_dia("Personal", fecha_str, df_personal_editado)
            if exito:
                st.success("¡Guardado!")
                st.rerun()

    with tab3:
        st.header("📁 Fichas Clínicas")
        lista_pacientes = obtener_lista_pacientes()
        if not lista_pacientes: st.info("Agrega un paciente primero.")
        else:
            paciente_seleccionado = st.selectbox("🔍 Selecciona un paciente:", ["-- Selecciona --"] + lista_pacientes, key="selector_paciente_unico")
            if paciente_seleccionado != "-- Selecciona --":
                df_fichas = cargar_tabla("Fichas")
                if df_fichas.empty or 'Paciente' not in df_fichas.columns: 
                    df_fichas = pd.DataFrame(columns=['Paciente', 'Teléfono', 'Edad', 'Diagnóstico', 'Notas Clínicas', 'Valor Sesión', 'Dirección'])
                if 'Valor Sesión' not in df_fichas.columns: df_fichas['Valor Sesión'] = "" 
                if 'Dirección' not in df_fichas.columns: df_fichas['Dirección'] = "" 
                
                if paciente_seleccionado not in df_fichas['Paciente'].values:
                    nueva_fila = pd.DataFrame({'Paciente': [paciente_seleccionado], 'Teléfono': [""], 'Edad': [""], 'Diagnóstico': [""], 'Notas Clínicas': [""], 'Valor Sesión': [""], 'Dirección': [""]})
                    df_fichas = pd.concat([df_fichas, nueva_fila], ignore_index=True)
                    guardar_tabla("Fichas", df_fichas)
                    
                idx_ficha = df_fichas.index[df_fichas['Paciente'] == paciente_seleccionado][0]
                tot_sesiones, tot_pagadas, tot_adeudadas = calcular_estadisticas_globales(paciente_seleccionado)
                
                col_met1, col_met2, col_met3 = st.columns(3)
                col_met1.metric("Sesiones", tot_sesiones)
                col_met2.metric("Pagadas ✅", tot_pagadas)
                col_met3.metric("Adeudadas ❌", tot_adeudadas)
                
                with st.form(key=f"form_ficha_{paciente_seleccionado}"):
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        nuevo_tel = st.text_input("📞 Teléfono:", value=str(df_fichas.at[idx_ficha, 'Teléfono']).replace('nan', ''))
                        nueva_edad = st.text_input("🎂 Edad:", value=str(df_fichas.at[idx_ficha, 'Edad']).replace('nan', ''))
                        nuevo_dir = st.text_input("📍 Dirección Base:", value=str(df_fichas.at[idx_ficha, 'Dirección']).replace('nan', ''), help="Se rellenará automáticamente en el calendario.")
                    with col_f2:
                        nuevo_diag = st.text_input("🩺 Diagnóstico:", value=str(df_fichas.at[idx_ficha, 'Diagnóstico']).replace('nan', ''))
                        nuevo_valor = st.text_input("💰 Valor Sesión (CLP):", value=str(df_fichas.at[idx_ficha, 'Valor Sesión']).replace('nan', ''))
                        st.markdown("<br>", unsafe_allow_html=True) 
                        
                    st.markdown("---")
                    nota_hoy = st.text_area("➕ Agregar evolución de hoy:", value="", height=100, help="Escribe aquí los detalles de la sesión. Al guardar, se añadirá al historial con la fecha automática.")
                    nuevas_notas = st.text_area("✍️ Historial Completo:", value=str(df_fichas.at[idx_ficha, 'Notas Clínicas']).replace('nan', ''), height=200, help="Puedes editar el historial pasado manualmente.")
                    
                    if st.form_submit_button("💾 Guardar Ficha"):
                        df_fichas.at[idx_ficha, 'Teléfono'] = nuevo_tel
                        df_fichas.at[idx_ficha, 'Edad'] = nueva_edad
                        df_fichas.at[idx_ficha, 'Dirección'] = nuevo_dir
                        df_fichas.at[idx_ficha, 'Diagnóstico'] = nuevo_diag
                        
                        texto_final = nuevas_notas
                        if nota_hoy.strip() != "":
                            fecha_actual = date.today().strftime("%d/%m/%Y")
                            if texto_final.strip() != "":
                                texto_final = f"{texto_final.strip()}\n\n📅 [{fecha_actual}] - {nota_hoy.strip()}"
                            else:
                                texto_final = f"📅 [{fecha_actual}] - {nota_hoy.strip()}"
                                
                        df_fichas.at[idx_ficha, 'Notas Clínicas'] = texto_final
                        df_fichas.at[idx_ficha, 'Valor Sesión'] = nuevo_valor
                        guardar_tabla("Fichas", df_fichas)
                        st.success("¡Ficha actualizada!")
                        time.sleep(1)
                        st.rerun()

    with tab4:
        st.header("📊 Dashboard General")
        mes_dashboard = st.date_input("Mes de referencia:", value=st.session_state.app_fecha_sel, key="mes_dashboard")
        stats = calcular_dashboard_mensual(mes_dashboard)
        col_d1, col_d2, col_d3 = st.columns(3)
        col_d1.metric("Sesiones totales", stats["total_sesiones"])
        col_d2.metric("💰 Ingresos", f"${stats['ingresos']:,.0f}".replace(",", "."))
        col_d3.metric("⏳ Por cobrar", f"${stats['por_cobrar']:,.0f}".replace(",", "."))

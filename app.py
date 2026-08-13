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

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
<style>
    .titulo-principal {
        color: #2C3E50;
        text-align: center;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 800;
        font-size: 3rem;
        margin-bottom: -10px;
    }
    .subtitulo {
        color: #18BC9C;
        text-align: center;
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 600;
        font-size: 1.5rem;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="titulo-principal">Centro de Comando</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitulo">Kinesiología CGM — Orden y Planificación</p>', unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE SHEETS (BLINDADA CONTRA ERROR 429) ---
@st.cache_resource
def conectar_bd():
    credenciales_json = json.loads(st.secrets["gcp_credentials"], strict=False)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(credenciales_json, scopes=scopes)
    cliente = gspread.authorize(creds)
    # Al retornar el doc aquí, Streamlit lo guarda y evita tocar la API excesivamente
    return cliente.open("Base_Datos_Kine")

try:
    doc = conectar_bd()
except Exception as e:
    st.error(f"Error conectando a la base de datos: {e}")
    st.stop()

def obtener_hoja(nombre):
    try:
        return doc.worksheet(nombre)
    except gspread.exceptions.WorksheetNotFound:
        return doc.add_worksheet(title=nombre, rows="1000", cols="20")

# 🛡️ Caché de Lectura
@st.cache_data(ttl=300)
def cargar_tabla(nombre_hoja):
    try:
        hoja = obtener_hoja(nombre_hoja)
        datos = hoja.get_all_records()
        return pd.DataFrame(datos) if datos else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def guardar_tabla(nombre_hoja, df):
    hoja = obtener_hoja(nombre_hoja)
    hoja.clear()
    if not df.empty:
        df_limpio = df.fillna("")
        hoja.update([df_limpio.columns.values.tolist()] + df_limpio.values.tolist())
    st.cache_data.clear()

# --- MEMORIA Y NAVEGACIÓN (BLINDADA) ---
if "app_fecha_sel" not in st.session_state:
    st.session_state.app_fecha_sel = date.today()
if "app_vista" not in st.session_state:
    st.session_state.app_vista = "calendario"
if "app_mes_cal" not in st.session_state:
    st.session_state.app_mes_cal = date.today().replace(day=1)

def ir_a_hoy():
    st.session_state.app_fecha_sel = date.today()
    st.session_state.app_mes_cal = date.today().replace(day=1)
    st.session_state.app_vista = "dia"

def cambiar_mes(delta):
    mes = st.session_state.app_mes_cal.month - 1 + delta
    año = st.session_state.app_mes_cal.year + mes // 12
    mes = mes % 12 + 1
    st.session_state.app_mes_cal = date(año, mes, 1)

# --- RUTAS PRINCIPALES DE VISTA ---
if st.session_state.app_vista == "calendario":
    # 📆 VISTA: CALENDARIO MENSUAL GIGANTE
    col_mes1, col_mes2, col_mes3 = st.columns([1, 2, 1])
    with col_mes1:
        st.button("⬅️ Mes Anterior", on_click=cambiar_mes, args=(-1,), use_container_width=True)
    with col_mes2:
        meses_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        año_act = st.session_state.app_mes_cal.year
        mes_act = st.session_state.app_mes_cal.month
        st.markdown(f"<h3 style='text-align: center; color: #2C3E50; margin-top: 0;'>{meses_es[mes_act-1]} {año_act}</h3>", unsafe_allow_html=True)
    with col_mes3:
        st.button("Mes Siguiente ➡️", on_click=cambiar_mes, args=(1,), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    cols_dias = st.columns(7)
    for i, d in enumerate(dias_semana):
        cols_dias[i].markdown(f"<div style='text-align:center; font-weight:bold; color:#18BC9C; padding-bottom: 10px;'>{d}</div>", unsafe_allow_html=True)

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
            else:
                cols[i].write("")

    st.markdown("<br><hr>", unsafe_allow_html=True)
    col_btn_hoy1, col_btn_hoy2, col_btn_hoy3 = st.columns([1, 2, 1])
    with col_btn_hoy2:
        st.button("🎯 Ir directamente al Día de Hoy", on_click=ir_a_hoy, use_container_width=True, type="primary")

else:
    # 📝 VISTA: DÍA SELECCIONADO (LAS PESTAÑAS)
    col_back, col_vacia, col_hoy = st.columns([1, 2, 1])
    with col_back:
        if st.button("📅 Volver al Calendario", use_container_width=True):
            st.session_state.app_vista = "calendario"
            st.rerun()
    with col_hoy:
        st.button("🎯 Ir a Hoy", on_click=ir_a_hoy, use_container_width=True)

    fecha_str = st.session_state.app_fecha_sel.strftime("%Y-%m-%d")
    fecha_visual = st.session_state.app_fecha_sel.strftime("%d/%m/%Y")

    horas_30_min = [
        "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", 
        "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", 
        "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", 
        "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00"
    ]

    # --- FUNCIONES DE BASE DE DATOS CENTRALIZADA ---
    def guardar_dia(tipo, fecha, df_dia):
        df_guardar = df_dia.copy()
        df_guardar.insert(0, 'Fecha', fecha)
        df_completo = cargar_tabla(tipo)
        
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_completo = df_completo[df_completo['Fecha'] != fecha]
            df_final = pd.concat([df_completo, df_guardar], ignore_index=True)
        else:
            df_final = df_guardar
        guardar_tabla(tipo, df_final)

    def cargar_datos_clinica(fecha):
        df_completo = cargar_tabla("Clinica")
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_dia = df_completo[df_completo['Fecha'] == fecha]
            if not df_dia.empty:
                return df_dia.drop(columns=['Fecha']).reset_index(drop=True)

        return pd.DataFrame({
            "Hora": horas_30_min, "Paciente": [""] * len(horas_30_min), "Detalle / Motivo": [""] * len(horas_30_min),
            "Dirección": [""] * len(horas_30_min), "Minutos de Viaje": [0] * len(horas_30_min), 
            "Hora de Salida": [""] * len(horas_30_min), "Ruta Maps": [""] * len(horas_30_min),
            "Estado": ["Libre 🟢"] * len(horas_30_min), "N° Sesión": [""] * len(horas_30_min), "Pago": ["-"] * len(horas_30_min),
            "Recordatorio": [""] * len(horas_30_min)
        })

    def cargar_datos_personal(fecha):
        df_completo = cargar_tabla("Personal")
        if not df_completo.empty and 'Fecha' in df_completo.columns:
            df_dia = df_completo[df_completo['Fecha'] == fecha]
            if not df_dia.empty:
                return df_dia.drop(columns=['Fecha']).reset_index(drop=True)

        return pd.DataFrame({
            "Hora": horas_30_min, "Actividad": [""] * len(horas_30_min), 
            "Categoría": ["-"] * len(horas_30_min), "Notas": [""] * len(horas_30_min)
        })

    def obtener_actividad_por_hora(df_personal):
        if df_personal.empty or 'Hora' not in df_personal.columns: return {}
        return dict(zip(df_personal['Hora'].astype(str).str.strip(), df_personal['Actividad'].astype(str).str.strip()))

    def calcular_tiempo_y_alarma(origen_coords_o_texto, destino, fecha_string, hora_string):
        try:
            geolocator = Nominatim(user_agent="sustancia_x_agenda", timeout=5)
            if isinstance(origen_coords_o_texto, tuple): coords_1 = origen_coords_o_texto 
            else:
                loc_origen = geolocator.geocode(origen_coords_o_texto + ", Valparaiso, Chile")
                if not loc_origen: return 0, "", ""
                coords_1 = (loc_origen.latitude, loc_origen.longitude)

            loc_destino = geolocator.geocode(destino + ", Valparaiso, Chile")
            if loc_destino:
                coords_2 = (loc_destino.latitude, loc_destino.longitude)
                distancia_km = geodesic(coords_1, coords_2).kilometers
                minutos_estimados = int((distancia_km * 2.5) + 5)
                tiempo_agendado = datetime.strptime(hora_string, "%H:%M")
                tiempo_salida = tiempo_agendado - timedelta(minutes=minutos_estimados)
                hora_salida_str = tiempo_salida.strftime("%H:%M")
                formato_fecha = fecha_string.replace("-", "")
                hora_inicio_cal = tiempo_salida.strftime("%H%M%S")
                hora_fin_cal = tiempo_agendado.strftime("%H%M%S")
                enlace_alarma = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text=🚗+SALIR:+Paciente&dates={formato_fecha}T{hora_inicio_cal}/{formato_fecha}T{hora_fin_cal}&details=Hora+de+salir+hacia:+{destino}"
                return minutos_estimados, hora_salida_str, enlace_alarma
        except Exception: pass
        return 0, "", ""

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
        df_pac = df_completo[(df_completo['Paciente'].str.strip().str.upper() == nombre_norm) & 
                             (~df_completo['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))]
        tot_sesiones = len(df_pac)
        pagadas = len(df_pac[df_pac['Pago'] == "Pagada ✅"])
        adeudadas = len(df_pac[df_pac['Pago'] == "No pagada ❌"])
        return tot_sesiones, pagadas, adeudadas

    def obtener_telefono_por_paciente():
        df_fichas = cargar_tabla("Fichas")
        if df_fichas.empty or 'Paciente' not in df_fichas.columns or 'Teléfono' not in df_fichas.columns: return {}
        return dict(zip(df_fichas['Paciente'].astype(str).str.strip().str.upper(), df_fichas['Teléfono'].astype(str).str.strip()))

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
        df_hist = df_completo[(df_completo['Paciente'].str.strip().str.upper() == nombre_norm) & 
                              (~df_completo['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))].copy()
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
    df_clinica['N° Sesión'] = df_clinica['N° Sesión'].fillna("").astype(str)
    df_clinica['Pago'] = df_clinica['Pago'].fillna("-").astype(str)
    if 'Recordatorio' not in df_clinica.columns: df_clinica['Recordatorio'] = ""
    df_clinica['Recordatorio'] = df_clinica['Recordatorio'].fillna("").astype(str)

    df_personal['Actividad'] = df_personal['Actividad'].fillna("").astype(str)
    df_personal['Categoría'] = df_personal['Categoría'].fillna("-").astype(str)
    df_personal['Notas'] = df_personal['Notas'].fillna("").astype(str)

    # --- 🛡️ AUTO-SINCRONIZACIÓN (CLÍNICA -> HORARIO PERSONAL) ---
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

    # --- 🤖 MAGIA AUTOMÁTICA DEL CALENDARIO ---
    mapa_personal = obtener_actividad_por_hora(df_personal) 
    mapa_telefonos = obtener_telefono_por_paciente()

    for index in df_clinica.index:
        paciente = str(df_clinica.at[index, 'Paciente']).strip()
        direccion = str(df_clinica.at[index, 'Dirección']).strip()
        hora_str = str(df_clinica.at[index, 'Hora']).strip()
        minutos = int(df_clinica.at[index, 'Minutos de Viaje'])
        pago_actual = str(df_clinica.at[index, 'Pago']).strip()
        sesion_actual = str(df_clinica.at[index, 'N° Sesión']).strip()
        detalle_actual = str(df_clinica.at[index, 'Detalle / Motivo']).strip()
        ruta_actual = str(df_clinica.at[index, 'Ruta Maps']).strip()
        
        actividad_personal = mapa_personal.get(hora_str, "") 
        
        es_tramite = (detalle_actual == "Personal / Trámite 🛑")
        es_gimnasio = (detalle_actual == "Gimnasio 🏋️")
        es_cita_clinica = (detalle_actual in ["Rehabilitación", "Entrenamiento", "Preventivo"])
        es_almuerzo = (paciente.upper() == "ALMUERZO")
        hay_paciente = (paciente != "" and not es_almuerzo)
        
        if hay_paciente or es_tramite or es_gimnasio or es_cita_clinica:
            if "calendar.google.com" not in ruta_actual:
                if direccion != "":
                    query_maps = urllib.parse.quote(direccion + ", Chile")
                    df_clinica.at[index, 'Ruta Maps'] = f"https://www.google.com/maps/search/?api=1&query={query_maps}"
                else: 
                    df_clinica.at[index, 'Ruta Maps'] = ""
                    
            try:
                tiempo_agendado = datetime.strptime(hora_str, "%H:%M")
                tiempo_salida = tiempo_agendado - timedelta(minutes=(minutos + 4))
                df_clinica.at[index, 'Hora de Salida'] = tiempo_salida.strftime("%H:%M")
            except: df_clinica.at[index, 'Hora de Salida'] = ""
                
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
            else:
                df_clinica.at[index, 'Recordatorio'] = ""
        else:
            df_clinica.at[index, 'Ruta Maps'] = ""; df_clinica.at[index, 'Hora de Salida'] = ""
            df_clinica.at[index, 'N° Sesión'] = ""; df_clinica.at[index, 'Pago'] = "-"
            df_clinica.at[index, 'Recordatorio'] = ""

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
                es_tramite_ant = (detalle_ant == "Personal / Trámite 🛑")
                es_gimnasio_ant = (detalle_ant == "Gimnasio 🏋️")
                es_cita_ant = (detalle_ant in ["Rehabilitación", "Entrenamiento", "Preventivo"])
                hay_paciente_ant = (paciente_ant != "" and paciente_ant.upper() != "ALMUERZO")
                
                if es_tramite_ant or es_gimnasio_ant:
                    nombre_bloqueo = paciente_ant if paciente_ant != "" else ("Trámite" if es_tramite_ant else "Gimnasio")
                    df_clinica.at[index, 'Estado'] = f"Bloqueado ({nombre_bloqueo}) ⏳"
                    continue
                elif es_cita_ant or hay_paciente_ant:
                    nombre_sesion = paciente_ant if paciente_ant != "" else "Paciente"
                    df_clinica.at[index, 'Estado'] = f"En sesión ({nombre_sesion}) ⏳"
                    continue
            df_clinica.at[index, 'Estado'] = "Libre 🟢"

    # --- SISTEMA DE PESTAÑAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["🩺 Calendario Clínico", "🕰️ Horario Personal", "📁 Fichas Clínicas", "📊 Dashboard"])

    with tab1:
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            st.header(f"📅 Agenda Clínica - {fecha_visual}")
        with col_t2:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            btn_guardar_clinica = st.button("💾 Guardar Cambios Clínicos", use_container_width=True, type="primary", key="btn_save_clinica")
        
        # --- NUEVO: BUSCADOR DE PACIENTES ---
        with st.expander("🔍 Buscador de Pacientes en el Calendario"):
            st.markdown("Encuentra rápidamente todas las fechas y horas en las que está agendado un paciente (ideal para borrar errores de tipeo o reagendar).")
            lista_pacientes_buscador = obtener_lista_pacientes()
            if not lista_pacientes_buscador:
                st.info("No hay pacientes agendados en el calendario.")
            else:
                paciente_buscar = st.selectbox("Selecciona un paciente a buscar:", ["-- Selecciona --"] + lista_pacientes_buscador, key="buscador_paciente_cal")
                if paciente_buscar != "-- Selecciona --":
                    df_full_clinica = cargar_tabla("Clinica")
                    if not df_full_clinica.empty and 'Paciente' in df_full_clinica.columns:
                        df_filtro = df_full_clinica[df_full_clinica['Paciente'].astype(str).str.strip().str.upper() == paciente_buscar.upper()]
                        if not df_filtro.empty:
                            df_resumen = df_filtro[['Fecha', 'Hora', 'Detalle / Motivo', 'Estado', 'Pago']].sort_values(by=['Fecha', 'Hora'])
                            st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                        else:
                            st.warning("No se encontraron sesiones agendadas para este paciente.")

        with st.expander("📍 Configuración de Viajes y Alarmas"):
            st.markdown("**1. Activa tu GPS (Permite el acceso a la ubicación si el navegador te lo pide):**")
            ubicacion_gps = streamlit_geolocation()
            st.markdown("**2. O escribe una dirección de salida manual (si no usas el GPS):**")
            direccion_base = st.text_input("Tu base:", value="Gomez Carreño, Viña del Mar")
            
            if st.button("⚡ Calcular Tiempos Automáticamente para hoy"):
                with st.spinner("Calculando rutas y generando alarmas..."):
                    origen_final = direccion_base
                    if ubicacion_gps and ubicacion_gps.get('latitude') is not None:
                        origen_final = (ubicacion_gps['latitude'], ubicacion_gps['longitude'])
                        st.info("🛰️ Coordenadas GPS obtenidas con éxito. Calculando distancias exactas...")
                    
                    for idx in df_clinica.index:
                        dir_paciente = str(df_clinica.at[idx, 'Dirección']).strip()
                        hora_paciente = str(df_clinica.at[idx, 'Hora']).strip()
                        
                        if dir_paciente != "":
                            minutos, h_salida, link_alarma = calcular_tiempo_y_alarma(origen_final, dir_paciente, fecha_str, hora_paciente)
                            if minutos > 0:
                                df_clinica.at[idx, 'Minutos de Viaje'] = minutos
                                df_clinica.at[idx, 'Hora de Salida'] = h_salida
                                df_clinica.at[idx, 'Ruta Maps'] = link_alarma
                    
                    guardar_dia("Clinica", fecha_str, df_clinica)
                    st.success("¡Tiempos calculados y alarmas generadas!")
                    st.rerun()

        with st.expander("🔄 Agendamiento Múltiple (Programar Paquetes)"):
            st.markdown("Agendamiento inteligente: La app revisará tanto el Calendario Clínico como tus bloqueos del Horario Personal para no generar topes.")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                m_paciente = st.text_input("Nombre del Paciente (Multisesión):")
                m_motivo = st.selectbox("Motivo:", ["Rehabilitación", "Entrenamiento", "Preventivo"])
                m_sesiones = st.number_input("Cantidad total de sesiones:", min_value=1, value=10, step=1)
            with col_m2:
                m_fecha_inicio = st.date_input("Comenzar a partir del:")
                m_hora = st.selectbox("Hora de la sesión:", horas_30_min)
                dias_map = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4, "Sábado": 5, "Domingo": 6}
                m_dias = st.multiselect("Días de la semana:", list(dias_map.keys()), default=["Lunes", "Miércoles"])
            with col_m3:
                m_direccion = st.text_input("Dirección (opcional):")
                m_viaje = st.number_input("Minutos de viaje:", min_value=0, value=0, step=1)
                st.markdown("<br>", unsafe_allow_html=True)
                btn_agendar = st.button("🚀 Programar Paquete Completo", use_container_width=True)

            if btn_agendar:
                if m_paciente.strip() == "": st.error("Debes ingresar el nombre del paciente.")
                elif not m_dias: st.error("Selecciona al menos un día de la semana.")
                else:
                    sesiones_logradas = 0
                    fecha_iter = m_fecha_inicio
                    dias_obj = [dias_map[d] for d in m_dias]
                    fechas_exitosas, fechas_ocupadas = [], []
                    dias_buscados = 0

                    with st.spinner('Revisando disponibilidad en la nube...'):
                        while sesiones_logradas < m_sesiones and dias_buscados < 365:
                            if fecha_iter.weekday() in dias_obj:
                                f_str = fecha_iter.strftime("%Y-%m-%d")
                                df_dia_futuro = cargar_datos_clinica(f_str)
                                df_pers_futuro = cargar_datos_personal(f_str)
                                mapa_personal_futuro = obtener_actividad_por_hora(df_pers_futuro) 
                                idx_hora = df_dia_futuro.index[df_dia_futuro['Hora'] == m_hora].tolist()
                                
                                if idx_hora:
                                    idx = idx_hora[0]
                                    ocupado = False
                                    
                                    p_act = str(df_dia_futuro.at[idx, 'Paciente']).strip()
                                    d_act = str(df_dia_futuro.at[idx, 'Detalle / Motivo']).strip()
                                    a_act = mapa_personal_futuro.get(m_hora, "")
                                    if p_act != "" or d_act in ["Personal / Trámite 🛑", "Gimnasio 🏋️"] or (a_act != "" and not a_act.startswith("🩺")): 
                                        ocupado = True
                                    
                                    if idx > 0 and not ocupado:
                                        p_ant = str(df_dia_futuro.at[idx-1, 'Paciente']).strip()
                                        d_ant = str(df_dia_futuro.at[idx-1, 'Detalle / Motivo']).strip()
                                        if (p_ant != "" and p_ant.upper() != "ALMUERZO") or (d_ant in ["Personal / Trámite 🛑", "Gimnasio 🏋️"]):
                                            ocupado = True
                                            
                                    if idx < len(df_dia_futuro) - 1 and not ocupado:
                                        p_sig = str(df_dia_futuro.at[idx+1, 'Paciente']).strip()
                                        d_sig = str(df_dia_futuro.at[idx+1, 'Detalle / Motivo']).strip()
                                        hora_sig = str(df_dia_futuro.at[idx+1, 'Hora']).strip() 
                                        a_sig = mapa_personal_futuro.get(hora_sig, "") 
                                        if p_sig != "" or d_sig in ["Personal / Trámite 🛑", "Gimnasio 🏋️"] or (a_sig != "" and not a_sig.startswith("🩺")):
                                            ocupado = True

                                    if not ocupado:
                                        df_dia_futuro.at[idx, 'Paciente'] = m_paciente
                                        df_dia_futuro.at[idx, 'Detalle / Motivo'] = m_motivo
                                        df_dia_futuro.at[idx, 'Dirección'] = m_direccion
                                        df_dia_futuro.at[idx, 'Minutos de Viaje'] = m_viaje
                                        df_dia_futuro.at[idx, 'Pago'] = "No pagada ❌"
                                        df_dia_futuro.at[idx, 'N° Sesión'] = "" 
                                        
                                        guardar_dia("Clinica", f_str, df_dia_futuro)
                                        fechas_exitosas.append(fecha_iter.strftime("%d/%m/%Y"))
                                        sesiones_logradas += 1
                                        time.sleep(0.3)
                                    else:
                                        fechas_ocupadas.append(fecha_iter.strftime("%d/%m/%Y"))
                                    
                            fecha_iter += timedelta(days=1)
                            dias_buscados += 1

                    if sesiones_logradas == m_sesiones:
                        st.success(f"✅ ¡Éxito! Se agendaron las {m_sesiones} sesiones.")
                        with st.expander("Ver fechas agendadas"): st.write(", ".join(fechas_exitosas))
                    else:
                        st.warning(f"⚠️ Solo se pudieron agendar {sesiones_logradas} sesiones.")
                    if fechas_ocupadas:
                        st.info(f"💡 Inteligencia de conflictos: Se omitieron estos días porque tenías un choque clínico o personal: {', '.join(fechas_ocupadas)}")
                    st.rerun()

        st.caption("💡 Para guardar: Si estás escribiendo en una celda, presiona **Enter** o haz clic fuera de ella antes de apretar el botón azul.")
        df_clinica_editado = st.data_editor(
            df_clinica, 
            use_container_width=True, 
            hide_index=True, 
            num_rows="dynamic",
            key=f"editor_clinica_{fecha_str}",
            column_order=("Hora", "Paciente", "Detalle / Motivo", "Dirección", "Minutos de Viaje", "Hora de Salida", "Ruta Maps", "Recordatorio", "Estado", "N° Sesión", "Pago"),
            column_config={
                "Detalle / Motivo": st.column_config.SelectboxColumn("Detalle / Motivo", options=["Rehabilitación", "Entrenamiento", "Preventivo", "Personal / Trámite 🛑", "Gimnasio 🏋️", "-"]),
                "Dirección": st.column_config.TextColumn("Dirección"),
                "Minutos de Viaje": st.column_config.NumberColumn("Minutos Viaje ⏱️", min_value=0, step=1),
                "Hora de Salida": st.column_config.TextColumn("Hora de Salida ⏰", disabled=True),
                "Ruta Maps": st.column_config.LinkColumn("🗺️ Navegación / 🔔 Alarma", disabled=True, display_text="Abrir Ruta/Alarma"),
                "Recordatorio": st.column_config.LinkColumn("📲 Recordatorio", disabled=True, display_text="Enviar WhatsApp", help="Requiere teléfono cargado en la Ficha Clínica del paciente."),
                "Estado": st.column_config.TextColumn("Estado", disabled=True),
                "N° Sesión": st.column_config.TextColumn("N° Sesión", help="Calculado automáticamente."),
                "Pago": st.column_config.SelectboxColumn("Pago", options=["No pagada ❌", "Pagada ✅", "-"])
            }
        )
        
        if btn_guardar_clinica:
            guardar_dia("Clinica", fecha_str, df_clinica_editado)
            guardar_dia("Personal", fecha_str, df_personal)
            st.success("¡Agenda guardada con éxito en la nube!")
            st.rerun()

    with tab2:
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            st.header(f"🕰️ Horario Personal - {fecha_visual}")
        with col_p2:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            btn_guardar_personal = st.button("💾 Guardar Horario Personal", use_container_width=True, type="primary", key="btn_save_personal")
            
        st.markdown("Escribe tus bloques de estudio (Tesis), salidas o descansos aquí. ¡Si agendas un paciente en la Clínica, se bloqueará automáticamente aquí!")
        
        df_personal_editado = st.data_editor(
            df_personal, 
            use_container_width=True, 
            hide_index=True, 
            num_rows="dynamic",
            key=f"editor_personal_{fecha_str}",
            column_order=("Hora", "Actividad", "Categoría", "Notas"),
            column_config={
                "Hora": st.column_config.TextColumn("Hora", disabled=True),
                "Actividad": st.column_config.TextColumn("Actividad Principal", help="Ej: Estudio Tesis, Almuerzo, Gimnasio..."),
                "Categoría": st.column_config.SelectboxColumn("Categoría", options=["Tesis Magíster", "Proyecto Sustancia X", "Mascota", "Salud", "Ocio", "Trámites", "Clínica", "General", "-"]),
                "Notas": st.column_config.TextColumn("Notas / Detalles")
            }
        )
        
        if btn_guardar_personal:
            guardar_dia("Personal", fecha_str, df_personal_editado)
            st.success("¡Horario guardado con éxito en la nube!")
            st.rerun()
        
        st.markdown("---")
        
        col_n1, col_n2 = st.columns([3, 1])
        with col_n1:
            st.markdown("### 📝 Notas Rápidas Generales")
        with col_n2:
            btn_guardar_notas = st.button("💾 Guardar Notas", use_container_width=True, type="primary", key="btn_save_notas")

        hoja_notas = obtener_hoja("Notas")
        try:
            nota_guardada_obj = hoja_notas.acell('A1')
            notas_guardadas = nota_guardada_obj.value if nota_guardada_obj.value else ""
        except:
            notas_guardadas = ""
        
        notas_actuales = st.text_area("Escribe aquí:", value=notas_guardadas, height=150, label_visibility="collapsed")
        
        if btn_guardar_notas:
            hoja_notas.update_acell('A1', notas_actuales)
            st.success("¡Notas actualizadas!")

    with tab3:
        st.header("📁 Fichas Clínicas y Evolución de Pacientes")
        lista_pacientes = obtener_lista_pacientes()
        if not lista_pacientes: st.info("Agrega un paciente en el Calendario Clínico para comenzar.")
        else:
            paciente_seleccionado = st.selectbox("🔍 Selecciona un paciente:", ["-- Selecciona --"] + lista_pacientes, key="selector_paciente_unico")
            
            if paciente_seleccionado != "-- Selecciona --":
                df_fichas = cargar_tabla("Fichas")
                if df_fichas.empty or 'Paciente' not in df_fichas.columns:
                    df_fichas = pd.DataFrame(columns=['Paciente', 'Teléfono', 'Edad', 'Diagnóstico', 'Notas Clínicas', 'Valor Sesión'])
                if 'Valor Sesión' not in df_fichas.columns:
                    df_fichas['Valor Sesión'] = "" 

                if paciente_seleccionado not in df_fichas['Paciente'].values:
                    nueva_fila = pd.DataFrame({'Paciente': [paciente_seleccionado], 'Teléfono': [""], 'Edad': [""], 'Diagnóstico': [""], 'Notas Clínicas': [""], 'Valor Sesión': [""]})
                    df_fichas = pd.concat([df_fichas, nueva_fila], ignore_index=True)
                    guardar_tabla("Fichas", df_fichas)
                    
                idx_ficha = df_fichas.index[df_fichas['Paciente'] == paciente_seleccionado][0]
                tot_sesiones, tot_pagadas, tot_adeudadas = calcular_estadisticas_globales(paciente_seleccionado)
                
                st.markdown("---")
                st.markdown(f"### 📊 Resumen Financiero: **{paciente_seleccionado}**")
                col_met1, col_met2, col_met3 = st.columns(3)
                col_met1.metric("Total Sesiones", tot_sesiones)
                col_met2.metric("Sesiones Pagadas ✅", tot_pagadas)
                col_met3.metric("Sesiones Adeudadas ❌", tot_adeudadas)
                
                st.markdown("---")
                with st.form(key=f"form_ficha_{paciente_seleccionado}"):
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        nuevo_tel = st.text_input("📞 Teléfono:", value=str(df_fichas.at[idx_ficha, 'Teléfono']))
                        nueva_edad = st.text_input("🎂 Edad:", value=str(df_fichas.at[idx_ficha, 'Edad']))
                    with col_f2:
                        nuevo_diag = st.text_input("🩺 Motivo de Consulta:", value=str(df_fichas.at[idx_ficha, 'Diagnóstico']))
                        nuevo_valor = st.text_input("💰 Valor Sesión (CLP):", value=str(df_fichas.at[idx_ficha, 'Valor Sesión']).replace('nan', ''), help="Se usa para calcular ingresos en el Dashboard.")
                    
                    nuevas_notas = st.text_area("✍️ Block de Notas (Evolución, OMNI-RES, RIR):", value=str(df_fichas.at[idx_ficha, 'Notas Clínicas']), height=250)
                    guardar_btn = st.form_submit_button("💾 Guardar Ficha Clínica")
                    
                    if guardar_btn:
                        df_fichas.at[idx_ficha, 'Teléfono'] = nuevo_tel.replace('nan', '')
                        df_fichas.at[idx_ficha, 'Edad'] = nueva_edad.replace('nan', '')
                        df_fichas.at[idx_ficha, 'Diagnóstico'] = nuevo_diag.replace('nan', '')
                        df_fichas.at[idx_ficha, 'Notas Clínicas'] = nuevas_notas.replace('nan', '')
                        df_fichas.at[idx_ficha, 'Valor Sesión'] = nuevo_valor.replace('nan', '')
                        guardar_tabla("Fichas", df_fichas)
                        st.success("¡Ficha actualizada de forma segura en la nube!")
                
                st.markdown("---")
                with st.expander("⚠️ Zona de Peligro: Eliminar Ficha"):
                    st.warning(f"Estás a punto de eliminar la ficha de **{paciente_seleccionado}**. Esto borrará sus datos personales y notas clínicas, pero NO borrará sus sesiones del calendario.")
                    confirmacion = st.checkbox(f"Confirmo que deseo eliminar la ficha de {paciente_seleccionado}")
                    if st.button("🗑️ Eliminar Ficha Permanentemente", type="primary", disabled=not confirmacion):
                        df_fichas = df_fichas[df_fichas['Paciente'] != paciente_seleccionado]
                        guardar_tabla("Fichas", df_fichas)
                        st.success("Ficha eliminada con éxito. Actualizando sistema...")
                        time.sleep(1.5)
                        st.rerun()

    with tab4:
        st.header("📊 Dashboard General")
        st.markdown("Ingresos, pagos y actividad agregada por mes. El cálculo de ingresos usa el **Valor Sesión** cargado en la Ficha Clínica de cada paciente.")

        mes_dashboard = st.date_input("Selecciona un mes de referencia:", value=st.session_state.app_fecha_sel, key="mes_dashboard")
        stats = calcular_dashboard_mensual(mes_dashboard)

        st.markdown(f"### Resumen de {mes_dashboard.strftime('%B %Y')}")
        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        col_d1.metric("Sesiones totales", stats["total_sesiones"])
        col_d2.metric("Sesiones pagadas ✅", stats["pagadas"])
        col_d3.metric("Sesiones adeudadas ❌", stats["adeudadas"])
        pct_deuda = (stats["pacientes_con_deuda"] / stats["pacientes_totales"] * 100) if stats["pacientes_totales"] > 0 else 0
        col_d4.metric("% pacientes con deuda", f"{pct_deuda:.0f}%")

        col_i1, col_i2 = st.columns(2)
        col_i1.metric("💰 Ingresos cobrados", f"${stats['ingresos']:,.0f}".replace(",", "."))
        col_i2.metric("⏳ Por cobrar", f"${stats['por_cobrar']:,.0f}".replace(",", "."))

        if stats["total_sesiones"] == 0:
            st.info("No hay sesiones registradas para este mes todavía.")
        st.caption("💡 Si el Valor Sesión de un paciente está vacío, sus sesiones no suman a los ingresos — cárgalo en la pestaña Fichas Clínicas.")

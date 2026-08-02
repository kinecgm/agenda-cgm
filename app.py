import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials
import json

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

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_sheets():
    credenciales_json = json.loads(st.secrets["gcp_credentials"], strict=False)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(credenciales_json, scopes=scopes)
    return gspread.authorize(creds)

try:
    cliente = conectar_sheets()
    doc = cliente.open("Base_Datos_Kine")
except Exception as e:
    st.error(f"Error conectando a la base de datos: {e}")
    st.stop()

def obtener_hoja(nombre):
    try:
        return doc.worksheet(nombre)
    except gspread.exceptions.WorksheetNotFound:
        return doc.add_worksheet(title=nombre, rows="1000", cols="20")

@st.cache_data(ttl=60)
def cargar_tabla(nombre_hoja):
    hoja = obtener_hoja(nombre_hoja)
    datos = hoja.get_all_records()
    return pd.DataFrame(datos) if datos else pd.DataFrame()

def guardar_tabla(nombre_hoja, df):
    hoja = obtener_hoja(nombre_hoja)
    hoja.clear()
    if not df.empty:
        hoja.update([df.columns.values.tolist()] + df.values.tolist())
    st.cache_data.clear()

# --- MEMORIA DE LA APLICACIÓN ---
if "fecha_memoria" not in st.session_state:
    st.session_state.fecha_memoria = date.today()

def ir_a_hoy():
    st.session_state.fecha_memoria = date.today()

# --- 🗓️ NAVEGADOR DE FECHAS ---
col1_fecha, col2_boton, col3_vacia = st.columns([1.5, 1, 2])
with col1_fecha:
    fecha_seleccionada = st.date_input("🗓️ Navegador de Días:", key="fecha_memoria")
with col2_boton:
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    st.button("🎯 Volver a Hoy", on_click=ir_a_hoy)

fecha_str = fecha_seleccionada.strftime("%Y-%m-%d")
fecha_visual = fecha_seleccionada.strftime("%d/%m/%Y")

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
            # EL ARREGLO ESTÁ AQUÍ ABAJO (reset_index)
            return df_dia.drop(columns=['Fecha']).reset_index(drop=True)

    return pd.DataFrame({
        "Hora": horas_30_min, "Paciente": [""] * len(horas_30_min), "Detalle / Motivo": [""] * len(horas_30_min),
        "Dirección": [""] * len(horas_30_min), "Minutos de Viaje": [0] * len(horas_30_min), 
        "Hora de Salida": [""] * len(horas_30_min), "Ruta Maps": [""] * len(horas_30_min),
        "Estado": ["Libre 🟢"] * len(horas_30_min), "N° Sesión": [""] * len(horas_30_min), "Pago": ["-"] * len(horas_30_min)
    })

def cargar_datos_personal(fecha):
    df_completo = cargar_tabla("Personal")
    if not df_completo.empty and 'Fecha' in df_completo.columns:
        df_dia = df_completo[df_completo['Fecha'] == fecha]
        if not df_dia.empty:
            # EL ARREGLO ESTÁ AQUÍ ABAJO (reset_index)
            return df_dia.drop(columns=['Fecha']).reset_index(drop=True)

    return pd.DataFrame({
        "Hora": horas_30_min, "Actividad": [""] * len(horas_30_min), 
        "Categoría": ["-"] * len(horas_30_min), "Notas": [""] * len(horas_30_min)
    })

# --- FUNCIONES DE ESTADÍSTICAS ---
def obtener_lista_pacientes():
    df_completo = cargar_tabla("Clinica")
    if df_completo.empty or 'Paciente' not in df_completo.columns: return []
    pacientes = set()
    for p in df_completo['Paciente'].dropna().unique():
        p_str = str(p).strip()
        if p_str != "" and p_str.upper() != "ALMUERZO":
            pacientes.add(p_str.title()) 
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

def calcular_sesion_historica(nombre_paciente, fecha_actual, hora_actual):
    if nombre_paciente == "": return ""
    nombre_norm = str(nombre_paciente).strip().upper()
    df_completo = cargar_tabla("Clinica")
    if df_completo.empty or 'Paciente' not in df_completo.columns: return "1"
    
    df_hist = df_completo[(df_completo['Paciente'].str.strip().str.upper() == nombre_norm) & 
                          (~df_completo['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))]
    
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

df_personal['Actividad'] = df_personal['Actividad'].fillna("").astype(str)
df_personal['Categoría'] = df_personal['Categoría'].fillna("-").astype(str)
df_personal['Notas'] = df_personal['Notas'].fillna("").astype(str)

# --- 🤖 MAGIA AUTOMÁTICA DEL CALENDARIO ---
for index in df_clinica.index:
    paciente = str(df_clinica.at[index, 'Paciente']).strip()
    direccion = str(df_clinica.at[index, 'Dirección']).strip()
    hora_str = str(df_clinica.at[index, 'Hora']).strip()
    minutos = int(df_clinica.at[index, 'Minutos de Viaje'])
    pago_actual = str(df_clinica.at[index, 'Pago']).strip()
    sesion_actual = str(df_clinica.at[index, 'N° Sesión']).strip()
    detalle_actual = str(df_clinica.at[index, 'Detalle / Motivo']).strip()
    
    actividad_personal = str(df_personal.at[index, 'Actividad']).strip() if index < len(df_personal) else ""
    
    es_tramite = (detalle_actual == "Personal / Trámite 🛑")
    es_gimnasio = (detalle_actual == "Gimnasio 🏋️")
    es_cita_clinica = (detalle_actual in ["Rehabilitación", "Entrenamiento", "Preventivo"])
    es_almuerzo = (paciente.upper() == "ALMUERZO")
    hay_paciente = (paciente != "" and not es_almuerzo)
    
    if hay_paciente or es_tramite or es_gimnasio or es_cita_clinica:
        if direccion != "":
            query_maps = urllib.parse.quote(direccion + ", Chile")
            df_clinica.at[index, 'Ruta Maps'] = f"https://www.google.com/maps/search/?api=1&query={query_maps}"
        else: df_clinica.at[index, 'Ruta Maps'] = ""
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
    else:
        df_clinica.at[index, 'Ruta Maps'] = ""; df_clinica.at[index, 'Hora de Salida'] = ""
        df_clinica.at[index, 'N° Sesión'] = ""; df_clinica.at[index, 'Pago'] = "-"

    if actividad_personal != "" and (hay_paciente or es_cita_clinica):
        df_clinica.at[index, 'Estado'] = "⚠️ TOPE HORARIO ⚠️"
    elif actividad_personal != "":
        df_clinica.at[index, 'Estado'] = f"Bloqueado ({actividad_personal}) 🛑"
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
tab1, tab2, tab3 = st.tabs(["🩺 Calendario Clínico", "🕰️ Horario Personal", "📁 Fichas Clínicas"])

with tab1:
    st.header(f"📅 Agenda Clínica - {fecha_visual}")
    
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
                            idx_hora = df_dia_futuro.index[df_dia_futuro['Hora'] == m_hora].tolist()
                            
                            if idx_hora:
                                idx = idx_hora[0]
                                ocupado = False
                                
                                p_act = str(df_dia_futuro.at[idx, 'Paciente']).strip()
                                d_act = str(df_dia_futuro.at[idx, 'Detalle / Motivo']).strip()
                                a_act = str(df_pers_futuro.at[idx, 'Actividad']).strip() if idx < len(df_pers_futuro) else ""
                                if p_act != "" or d_act in ["Personal / Trámite 🛑", "Gimnasio 🏋️"] or a_act != "": 
                                    ocupado = True
                                
                                if idx > 0 and not ocupado:
                                    p_ant = str(df_dia_futuro.at[idx-1, 'Paciente']).strip()
                                    d_ant = str(df_dia_futuro.at[idx-1, 'Detalle / Motivo']).strip()
                                    if (p_ant != "" and p_ant.upper() != "ALMUERZO") or (d_ant in ["Personal / Trámite 🛑", "Gimnasio 🏋️"]):
                                        ocupado = True
                                        
                                if idx < len(df_dia_futuro) - 1 and not ocupado:
                                    p_sig = str(df_dia_futuro.at[idx+1, 'Paciente']).strip()
                                    d_sig = str(df_dia_futuro.at[idx+1, 'Detalle / Motivo']).strip()
                                    a_sig = str(df_pers_futuro.at[idx+1, 'Actividad']).strip() if (idx+1) < len(df_pers_futuro) else ""
                                    if p_sig != "" or d_sig in ["Personal / Trámite 🛑", "Gimnasio 🏋️"] or a_sig != "":
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

    df_clinica_editado = st.data_editor(
        df_clinica, use_container_width=True, hide_index=True, num_rows="dynamic",
        column_order=("Hora", "Paciente", "Detalle / Motivo", "Dirección", "Minutos de Viaje", "Hora de Salida", "Ruta Maps", "Estado", "N° Sesión", "Pago"),
        column_config={
            "Detalle / Motivo": st.column_config.SelectboxColumn("Detalle / Motivo", options=["Rehabilitación", "Entrenamiento", "Preventivo", "Personal / Trámite 🛑", "Gimnasio 🏋️", "-"]),
            "Dirección": st.column_config.TextColumn("Dirección"),
            "Minutos de Viaje": st.column_config.NumberColumn("Minutos Viaje ⏱️", min_value=0, step=1),
            "Hora de Salida": st.column_config.TextColumn("Hora de Salida ⏰", disabled=True),
            "Ruta Maps": st.column_config.LinkColumn("🗺️ Navegación", disabled=True, display_text="Abrir Mapa"),
            "Estado": st.column_config.TextColumn("Estado", disabled=True),
            "N° Sesión": st.column_config.TextColumn("N° Sesión", help="Calculado automáticamente."),
            "Pago": st.column_config.SelectboxColumn("Pago", options=["No pagada ❌", "Pagada ✅", "-"])
        }
    )
    
    if not df_clinica.equals(df_clinica_editado): 
        guardar_dia("Clinica", fecha_str, df_clinica_editado)
        st.rerun()

with tab2:
    st.header(f"🕰️ Horario Personal - {fecha_visual}")
    st.markdown("Escribe tus bloques de estudio, salidas o descansos aquí. Se bloquearán automáticamente en el Calendario Clínico.")
    
    df_personal_editado = st.data_editor(
        df_personal, use_container_width=True, hide_index=True, num_rows="dynamic",
        column_order=("Hora", "Actividad", "Categoría", "Notas"),
        column_config={
            "Hora": st.column_config.TextColumn("Hora", disabled=True),
            "Actividad": st.column_config.TextColumn("Actividad Principal", help="Ej: Estudio, Almuerzo, Gimnasio..."),
            "Categoría": st.column_config.SelectboxColumn("Categoría", options=["Tesis Magíster", "Proyecto Sustancia X", "Mascota", "Salud", "Ocio", "Trámites", "General", "-"]),
            "Notas": st.column_config.TextColumn("Notas / Detalles")
        }
    )
    
    if not df_personal.equals(df_personal_editado):
        guardar_dia("Personal", fecha_str, df_personal_editado)
        st.rerun()
    
    st.markdown("---")
    hoja_notas = obtener_hoja("Notas")
    nota_guardada_obj = hoja_notas.acell('A1')
    notas_guardadas = nota_guardada_obj.value if nota_guardada_obj.value else ""
    
    notas_actuales = st.text_area("Notas Rápidas Generales:", value=notas_guardadas, height=150)
    if notas_actuales != notas_guardadas:
        hoja_notas.update_acell('A1', notas_actuales)

with tab3:
    st.header("📁 Fichas Clínicas y Evolución de Pacientes")
    lista_pacientes = obtener_lista_pacientes()
    if not lista_pacientes: st.info("Agrega un paciente en el Calendario Clínico para comenzar.")
    else:
        paciente_seleccionado = st.selectbox("🔍 Selecciona un paciente:", ["-- Selecciona --"] + lista_pacientes)
        if paciente_seleccionado != "-- Selecciona --":
            df_fichas = cargar_tabla("Fichas")
            if df_fichas.empty or 'Paciente' not in df_fichas.columns:
                df_fichas = pd.DataFrame(columns=['Paciente', 'Teléfono', 'Edad', 'Diagnóstico', 'Notas Clínicas'])
                
            if paciente_seleccionado not in df_fichas['Paciente'].values:
                nueva_fila = pd.DataFrame({'Paciente': [paciente_seleccionado], 'Teléfono': [""], 'Edad': [""], 'Diagnóstico': [""], 'Notas Clínicas': [""]})
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
                
                nuevas_notas = st.text_area("✍️ Block de Notas (Evolución, OMNI-RES, RIR):", value=str(df_fichas.at[idx_ficha, 'Notas Clínicas']), height=250)
                guardar_btn = st.form_submit_button("💾 Guardar Ficha Clínica")
                
                if guardar_btn:
                    df_fichas.at[idx_ficha, 'Teléfono'] = nuevo_tel.replace('nan', '')
                    df_fichas.at[idx_ficha, 'Edad'] = nueva_edad.replace('nan', '')
                    df_fichas.at[idx_ficha, 'Diagnóstico'] = nuevo_diag.replace('nan', '')
                    df_fichas.at[idx_ficha, 'Notas Clínicas'] = nuevas_notas.replace('nan', '')
                    guardar_tabla("Fichas", df_fichas)
                    st.success("¡Ficha actualizada de forma segura en la nube!")

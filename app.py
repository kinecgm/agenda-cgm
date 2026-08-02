import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import os
import urllib.parse

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

# --- MEMORIA DE LA APLICACIÓN ---
if "fecha_memoria" not in st.session_state:
    st.session_state.fecha_memoria = date.today()

def ir_a_hoy():
    st.session_state.fecha_memoria = date.today()

# --- 🗓️ NAVEGADOR DE FECHAS Y BOTÓN ---
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

# --- FUNCIONES DE FICHAS Y ESTADÍSTICAS ---
def obtener_lista_pacientes():
    pacientes = set()
    archivos = [f for f in os.listdir('.') if f.startswith('agenda_clinica_') and f.endswith('.csv')]
    for archivo in archivos:
        try:
            df_temp = pd.read_csv(archivo)
            if 'Paciente' in df_temp.columns:
                for p in df_temp['Paciente'].dropna().unique():
                    p_str = str(p).strip()
                    if p_str != "" and p_str.upper() != "ALMUERZO":
                        pacientes.add(p_str.title()) 
        except: pass
    return sorted(list(pacientes))

def calcular_estadisticas_globales(nombre_paciente):
    nombre_norm = str(nombre_paciente).strip().upper()
    total_sesiones = 0
    pagadas = 0
    adeudadas = 0
    archivos = [f for f in os.listdir('.') if f.startswith('agenda_clinica_') and f.endswith('.csv')]
    for archivo in archivos:
        try:
            df_temp = pd.read_csv(archivo)
            if 'Paciente' in df_temp.columns:
                for idx, row in df_temp.iterrows():
                    pac_fila = str(row['Paciente']).strip().upper()
                    detalle_fila = str(row.get('Detalle / Motivo', '')).strip()
                    pago_fila = str(row.get('Pago', '')).strip()
                    if pac_fila == nombre_norm and detalle_fila not in ["Personal / Trámite 🛑", "Gimnasio 🏋️"]:
                        total_sesiones += 1
                        if pago_fila == "Pagada ✅": pagadas += 1
                        elif pago_fila == "No pagada ❌": adeudadas += 1
        except: pass
    return total_sesiones, pagadas, adeudadas

def cargar_bd_fichas():
    if os.path.exists('fichas_clinicas_db.csv'): return pd.read_csv('fichas_clinicas_db.csv')
    return pd.DataFrame(columns=['Paciente', 'Teléfono', 'Edad', 'Diagnóstico', 'Notas Clínicas'])

def guardar_bd_fichas(df_fichas):
    df_fichas.to_csv('fichas_clinicas_db.csv', index=False)

def calcular_sesion_historica(nombre_paciente, fecha_actual, hora_actual):
    if nombre_paciente == "": return ""
    nombre_normalizado = str(nombre_paciente).strip().upper()
    archivos = [f for f in os.listdir('.') if f.startswith('agenda_clinica_') and f.endswith('.csv')]
    archivos.sort()
    contador = 0
    for archivo in archivos:
        fecha_archivo = archivo.replace('agenda_clinica_', '').replace('.csv', '')
        if fecha_archivo > fecha_actual: continue
        try:
            df_temp = pd.read_csv(archivo)
            if 'Paciente' in df_temp.columns:
                for idx, row in df_temp.iterrows():
                    pac_fila = str(row['Paciente']).strip().upper()
                    hora_fila = str(row['Hora']).strip()
                    detalle_fila = str(row.get('Detalle / Motivo', '')).strip()
                    if pac_fila == nombre_normalizado and detalle_fila not in ["Personal / Trámite 🛑", "Gimnasio 🏋️"]:
                        if fecha_archivo == fecha_actual:
                            if hora_fila <= hora_actual: contador += 1
                        else: contador += 1
        except: pass
    return str(contador)

# --- BODEGA DE DATOS DINÁMICA ---
def cargar_datos_clinica(fecha):
    archivo = f'agenda_clinica_{fecha}.csv'
    if os.path.exists(archivo):
        df = pd.read_csv(archivo)
        if 'Dirección' not in df.columns: df.insert(3, 'Dirección', "")
        if 'Minutos de Viaje' not in df.columns: df.insert(4, 'Minutos de Viaje', 0)
        if 'Hora de Salida' not in df.columns: df.insert(5, 'Hora de Salida', "")
        if 'Ruta Maps' not in df.columns: df.insert(6, 'Ruta Maps', "")
        if 'N° Sesión' not in df.columns: df.insert(8, 'N° Sesión', "")
        if 'Pago' not in df.columns: df.insert(9, 'Pago', "-")
        if len(df) < 20:
            df_nuevo = pd.DataFrame({"Hora": horas_30_min})
            df = df_nuevo.merge(df, on="Hora", how="left").fillna("")
            df['Minutos de Viaje'] = pd.to_numeric(df['Minutos de Viaje'], errors='coerce').fillna(0).astype(int)
        return df
    else:
        return pd.DataFrame({
            "Hora": horas_30_min, "Paciente": [""] * len(horas_30_min), "Detalle / Motivo": [""] * len(horas_30_min),
            "Dirección": [""] * len(horas_30_min), "Minutos de Viaje": [0] * len(horas_30_min), 
            "Hora de Salida": [""] * len(horas_30_min), "Ruta Maps": [""] * len(horas_30_min),
            "Estado": ["Libre 🟢"] * len(horas_30_min), "N° Sesión": [""] * len(horas_30_min), "Pago": ["-"] * len(horas_30_min)
        })

def cargar_datos_personal(fecha):
    archivo = f'agenda_personal_{fecha}.csv'
    if os.path.exists(archivo): 
        df = pd.read_csv(archivo)
        # Si detecta el formato antiguo estático, lo actualiza silenciosamente a la grilla de 30 mins
        if 'Bloque Horario' in df.columns or len(df) < 20:
            return pd.DataFrame({"Hora": horas_30_min, "Actividad": [""] * len(horas_30_min), "Categoría": ["-"] * len(horas_30_min), "Notas": [""] * len(horas_30_min)})
        return df
    else:
        return pd.DataFrame({
            "Hora": horas_30_min,
            "Actividad": [""] * len(horas_30_min),
            "Categoría": ["-"] * len(horas_30_min),
            "Notas": [""] * len(horas_30_min)
        })

df_clinica = cargar_datos_clinica(fecha_str)
df_personal = cargar_datos_personal(fecha_str)

# --- PROTECCIÓN DE DATOS ---
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

# --- 🤖 MAGIA AUTOMÁTICA DEL CALENDARIO (CON ESPEJO PERSONAL) ---
for index in df_clinica.index:
    paciente = str(df_clinica.at[index, 'Paciente']).strip()
    direccion = str(df_clinica.at[index, 'Dirección']).strip()
    hora_str = str(df_clinica.at[index, 'Hora']).strip()
    minutos = int(df_clinica.at[index, 'Minutos de Viaje'])
    pago_actual = str(df_clinica.at[index, 'Pago']).strip()
    sesion_actual = str(df_clinica.at[index, 'N° Sesión']).strip()
    detalle_actual = str(df_clinica.at[index, 'Detalle / Motivo']).strip()
    
    # Extraemos qué está pasando en tu vida personal en este mismo bloque
    actividad_personal = str(df_personal.at[index, 'Actividad']).strip()
    
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

    # --- CONTROL DE ESTADOS Y ESPEJO PERSONAL ---
    # Si hay algo en el calendario personal Y en el clínico al mismo tiempo:
    if actividad_personal != "" and (hay_paciente or es_cita_clinica):
        df_clinica.at[index, 'Estado'] = "⚠️ TOPE HORARIO ⚠️"
    
    # Si hay una actividad personal, bloquea automáticamente el clínico:
    elif actividad_personal != "":
        df_clinica.at[index, 'Estado'] = f"Bloqueado ({actividad_personal}) 🛑"
        
    elif es_tramite: df_clinica.at[index, 'Estado'] = "Bloqueado 🛑"
    elif es_gimnasio: df_clinica.at[index, 'Estado'] = "Gimnasio 🏋️"
    elif es_cita_clinica or hay_paciente: df_clinica.at[index, 'Estado'] = "Agendado 🔒"
    elif es_almuerzo: df_clinica.at[index, 'Estado'] = "-"
    else:
        # Fantasmas (bloqueos de la sesión anterior de 60 mins)
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
                fechas_exitosas = []
                fechas_ocupadas = []
                dias_buscados = 0

                with st.spinner('Revisando disponibilidad clínica y personal en el futuro...'):
                    while sesiones_logradas < m_sesiones and dias_buscados < 365:
                        if fecha_iter.weekday() in dias_obj:
                            f_str = fecha_iter.strftime("%Y-%m-%d")
                            df_dia_futuro = cargar_datos_clinica(f_str)
                            df_pers_futuro = cargar_datos_personal(f_str)
                            idx_hora = df_dia_futuro.index[df_dia_futuro['Hora'] == m_hora].tolist()
                            
                            if idx_hora:
                                idx = idx_hora[0]
                                ocupado = False
                                
                                # 1. ¿Está la celda ocupada en la Clínica o en lo Personal?
                                p_act = str(df_dia_futuro.at[idx, 'Paciente']).strip()
                                d_act = str(df_dia_futuro.at[idx, 'Detalle / Motivo']).strip()
                                a_act = str(df_pers_futuro.at[idx, 'Actividad']).strip() if idx < len(df_pers_futuro) else ""
                                if p_act != "" or d_act in ["Personal / Trámite 🛑", "Gimnasio 🏋️"] or a_act != "": 
                                    ocupado = True
                                
                                # 2. ¿Nos pisa un bloque clínico de la hora anterior?
                                if idx > 0 and not ocupado:
                                    p_ant = str(df_dia_futuro.at[idx-1, 'Paciente']).strip()
                                    d_ant = str(df_dia_futuro.at[idx-1, 'Detalle / Motivo']).strip()
                                    if (p_ant != "" and p_ant.upper() != "ALMUERZO") or (d_ant in ["Personal / Trámite 🛑", "Gimnasio 🏋️"]):
                                        ocupado = True
                                        
                                # 3. ¿Está libre la media hora SIGUIENTE (clínica o personal) para nuestros 60 mins?
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
                                    df_dia_futuro.to_csv(f'agenda_clinica_{f_str}.csv', index=False)
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
    df_clinica_editado.to_csv(f'agenda_clinica_{fecha_str}.csv', index=False)
    if not df_clinica.equals(df_clinica_editado): st.rerun()

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
    df_personal_editado.to_csv(f'agenda_personal_{fecha_str}.csv', index=False)
    if not df_personal.equals(df_personal_editado): st.rerun()
    
    st.markdown("---")
    notas_guardadas = ""
    if os.path.exists('notas_mentales.txt'):
        with open('notas_mentales.txt', 'r', encoding='utf-8') as f: notas_guardadas = f.read()
    
    notas_actuales = st.text_area("Notas Rápidas Generales:", value=notas_guardadas, height=150)
    if notas_actuales != notas_guardadas:
        with open('notas_mentales.txt', 'w', encoding='utf-8') as f: f.write(notas_actuales)

with tab3:
    st.header("📁 Fichas Clínicas y Evolución de Pacientes")
    lista_pacientes = obtener_lista_pacientes()
    if not lista_pacientes: st.info("Agrega un paciente en el Calendario Clínico para comenzar.")
    else:
        paciente_seleccionado = st.selectbox("🔍 Selecciona un paciente:", ["-- Selecciona --"] + lista_pacientes)
        if paciente_seleccionado != "-- Selecciona --":
            df_fichas = cargar_bd_fichas()
            if paciente_seleccionado not in df_fichas['Paciente'].values:
                nueva_fila = pd.DataFrame({'Paciente': [paciente_seleccionado], 'Teléfono': [""], 'Edad': [""], 'Diagnóstico': [""], 'Notas Clínicas': [""]})
                df_fichas = pd.concat([df_fichas, nueva_fila], ignore_index=True)
                guardar_bd_fichas(df_fichas)
                
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
                    guardar_bd_fichas(df_fichas)
                    st.success("¡Ficha actualizada!")
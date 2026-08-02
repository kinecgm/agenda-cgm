import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd

# Configuración inicial
st.set_page_config(page_title="Agenda Kine CGM", page_icon="📅")
st.title("📅 Agenda Kinesiología CGM")

# Función para conectar a Google Sheets
def conectar_sheets():
    # El secreto está aquí: strict=False hace que ignore los errores de formato del Mac
    credenciales_json = json.loads(st.secrets["gcp_credentials"], strict=False)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(credenciales_json, scopes=scopes)
    cliente = gspread.authorize(creds)
    return cliente

# Conectarnos y abrir el Excel
try:
    cliente = conectar_sheets()
    hoja = cliente.open("Base_Datos_Kine").sheet1
except Exception as e:
    st.error(f"Error conectando al Excel: {e}")
    st.stop()

# Interfaz para agregar pacientes
st.subheader("➕ Agendar Nuevo Paciente")
with st.form("nuevo_paciente"):
    fecha = st.date_input("Fecha")
    hora = st.time_input("Hora")
    paciente = st.text_input("Nombre del Paciente")
    motivo = st.selectbox("Motivo", ["Evaluación Kinesiológica", "Rehabilitación", "Entrenamiento de Fuerza", "Otro"])
    
    enviado = st.form_submit_button("Guardar Cita")
    
    if enviado:
        if paciente:
            fecha_str = fecha.strftime("%Y-%m-%d")
            hora_str = hora.strftime("%H:%M")
            # Insertar en Excel
            hoja.append_row([fecha_str, hora_str, paciente, motivo])
            st.success(f"✅ ¡Cita de {paciente} guardada con éxito en tu Excel!")
        else:
            st.warning("⚠️ Por favor, ingresa el nombre del paciente.")

# Mostrar la agenda actual
st.subheader("📋 Próximas Citas")
try:
    datos = hoja.get_all_records()
    if datos:
        df = pd.DataFrame(datos)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay pacientes agendados todavía.")
except Exception as e:
    st.error(f"No pudimos leer los datos: {e}")

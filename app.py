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
                col_met1.metric("Sesiones Totales", tot_sesiones)
                col_met2.metric("Pagadas ✅", tot_pagadas)
                col_met3.metric("Adeudadas ❌", tot_adeudadas)

                # --- NUEVO: TABLA DE HISTORIAL DE SESIONES ---
                st.markdown("### 🗓️ Historial de Sesiones en Calendario")
                df_full_clinica_hist = cargar_tabla("Clinica")
                if not df_full_clinica_hist.empty and 'Paciente' in df_full_clinica_hist.columns:
                    df_filtro_pac = df_full_clinica_hist[(df_full_clinica_hist['Paciente'].astype(str).str.strip().str.upper() == paciente_seleccionado.upper()) & (~df_full_clinica_hist['Detalle / Motivo'].isin(["Personal / Trámite 🛑", "Gimnasio 🏋️"]))]
                    if not df_filtro_pac.empty:
                        # Seleccionar columnas útiles y ordenar por fecha descendente
                        df_mostrar = df_filtro_pac[['Fecha', 'Hora', 'Detalle / Motivo', 'Pago']].sort_values(by=['Fecha', 'Hora'], ascending=[False, False])
                        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
                    else:
                        st.info("No hay sesiones registradas en el calendario para este paciente.")
                
                st.markdown("---")
                
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
                        
                    nota_hoy = st.text_area("➕ Agregar evolución de hoy:", value="", height=100)
                    nuevas_notas = st.text_area("✍️ Historial Clínico Completo:", value=str(df_fichas.at[idx_ficha, 'Notas Clínicas']).replace('nan', ''), height=200)
                    
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

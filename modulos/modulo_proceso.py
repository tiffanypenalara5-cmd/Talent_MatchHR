# modulo_proceso.py
# Funciones nuevas de TalentMatch HR: aviso de ley, vacantes,
# terna, estados, sesiones y tiempos.

import csv
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

# Carpeta donde se guardarán los archivos de datos
os.makedirs("datos", exist_ok=True)
ARCHIVO_VACANTES = "datos/vacantes_guardadas.json"
ARCHIVO_SESIONES = "datos/sesiones.csv"
ESTADOS = ["Preseleccionado", "Entrevista", "Descartado", "Contratado"]


# ---------------------------------------------------------------
# AVISO LEY 8968 Y AUTORIZACIÓN
# ---------------------------------------------------------------
def aviso_ley_8968():
    st.info(
        "Aviso Ley 8968 (Protección de la persona frente al "
        "tratamiento de sus datos personales): esta herramienta "
        "procesa datos únicamente con fines académicos. "
        "Todos los datos usados son ficticios."
    )
    acepta = st.checkbox(
        "Autorizo el tratamiento de los datos con fines académicos"
    )
    if not acepta:
        st.warning("Debe aceptar la autorización para continuar.")
    elif "inicio_proyecto" not in st.session_state:
        st.session_state["inicio_proyecto"] = datetime.now()
    return acepta


# ---------------------------------------------------------------
# REGISTRO DE SESIONES
# ---------------------------------------------------------------
def registrar_sesion(accion):
    es_nuevo = not os.path.exists(ARCHIVO_SESIONES)
    with open(ARCHIVO_SESIONES, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if es_nuevo:
            escritor.writerow(["fecha_hora", "accion"])
        escritor.writerow(
            [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), accion]
        )


# ---------------------------------------------------------------
# TERNA: COMPARADOR DE CANDIDATOS CON JUSTIFICACIÓN
# ---------------------------------------------------------------
def justificar_terna(elegidos, resto):
    """Arma las razones de la terna usando los datos de cada candidato."""
    ordenados = sorted(elegidos, key=lambda c: c["confirmado"], reverse=True)
    lineas = []

    for posicion, c in enumerate(ordenados, start=1):
        cumple = c.get("cumple", 0)
        sin_evidencia = c.get("sin_evidencia", 0)
        total = cumple + c.get("no_cumple", 0) + sin_evidencia
        texto = (
            f"**{posicion}.º {c['nombre']}**: puntaje confirmado "
            f"{c['confirmado']} de 100; cumple {cumple} de {total} criterios"
        )
        if sin_evidencia > 0:
            margen = c["posible"] - c["confirmado"]
            texto += (
                f"; tiene {sin_evidencia} criterio(s) sin evidencia, por lo "
                f"que podría llegar a {c['posible']} (+{margen} puntos) y "
                f"se recomienda revisión manual"
            )
        lineas.append(texto)

    if resto:
        menor_terna = min(c["confirmado"] for c in elegidos)
        mejor_fuera = max(c["confirmado"] for c in resto)
        if mejor_fuera <= menor_terna:
            lineas.append(
                f"Ningún candidato fuera de la terna supera el menor puntaje "
                f"confirmado de la terna ({menor_terna}); el mejor de los "
                f"excluidos tiene {mejor_fuera}."
            )
        else:
            lineas.append(
                f"Atención: hay un candidato fuera de la terna con "
                f"{mejor_fuera} puntos confirmados, más que el menor de la "
                f"terna ({menor_terna}). Debe quedar justificado el motivo."
            )
    return lineas


def panel_terna(candidatos):
    st.subheader("Terna de candidatos")
    nombres = [c["nombre"] for c in candidatos]
    elegidos = st.multiselect(
        "Elija hasta 3 candidatos", nombres, max_selections=3
    )

    if not elegidos:
        st.caption("Aún no ha elegido candidatos para la terna.")
        return

    filas = [c for c in candidatos if c["nombre"] in elegidos]
    resto = [c for c in candidatos if c["nombre"] not in elegidos]

    st.table(pd.DataFrame(filas).set_index("nombre").T)

    with st.expander("¿Por qué esta terna? Ver justificación con datos"):
        for linea in justificar_terna(filas, resto):
            st.markdown("- " + linea)
        st.caption(
            "Esta justificación se calcula con los datos del ranking. "
            "La decisión final es del profesional de Recursos Humanos."
        )

    if st.session_state.get("ultima_terna") != elegidos:
        registrar_sesion("Terna creada: " + ", ".join(elegidos))
        st.session_state["ultima_terna"] = elegidos


        # ---------------------------------------------------------------
# BANCO DE CANDIDATOS (para futuras vacantes)
# ---------------------------------------------------------------
ARCHIVO_BANCO = "datos/banco_candidatos.csv"
COLUMNAS_BANCO = [
    "fecha", "vacante", "nombre", "confirmado", "posible",
    "cumple", "no_cumple", "sin_evidencia", "estado",
]


def cargar_banco():
    if os.path.exists(ARCHIVO_BANCO):
        return pd.read_csv(ARCHIVO_BANCO)
    return pd.DataFrame(columns=COLUMNAS_BANCO)


def guardar_en_banco(candidatos, vacante):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    filas = []
    for c in candidatos:
        filas.append({
            "fecha": ahora,
            "vacante": vacante,
            "nombre": c["nombre"],
            "confirmado": c["confirmado"],
            "posible": c["posible"],
            "cumple": c.get("cumple", 0),
            "no_cumple": c.get("no_cumple", 0),
            "sin_evidencia": c.get("sin_evidencia", 0),
            "estado": c.get("estado", "Preseleccionado"),
        })
    nuevos = pd.DataFrame(filas, columns=COLUMNAS_BANCO)
    todos = pd.concat([cargar_banco(), nuevos], ignore_index=True)
    # Si el mismo candidato ya estaba en esa vacante, se queda la versión nueva
    todos = todos.drop_duplicates(subset=["nombre", "vacante"], keep="last")
    todos.to_csv(ARCHIVO_BANCO, index=False, encoding="utf-8")
    registrar_sesion(f"Banco: {len(nuevos)} candidato(s) guardado(s) ({vacante})")
    return len(nuevos)


def panel_banco(candidatos):
    st.subheader("Banco de candidatos")
    st.caption(
        "Se guardan solo datos de evaluación. No se guardan edad, sexo, "
        "estado civil ni otros datos personales (Ley 8968). Datos ficticios."
    )

    vacante = st.session_state.get("nombre_vacante", "Sin nombre")
    if st.button("Guardar candidatos en el banco"):
        cantidad = guardar_en_banco(candidatos, vacante)
        st.success(f"Se guardaron {cantidad} candidato(s) de la vacante: {vacante}")

    banco = cargar_banco()
    if banco.empty:
        st.caption("El banco todavía está vacío.")
        return

    col1, col2 = st.columns(2)
    opciones = ["Todas"] + sorted(banco["vacante"].unique().tolist())
    filtro_vacante = col1.selectbox("Vacante", opciones)
    minimo = col2.slider("Puntaje confirmado mínimo", 0, 100, 0)

    vista = banco[banco["confirmado"] >= minimo]
    if filtro_vacante != "Todas":
        vista = vista[vista["vacante"] == filtro_vacante]

    st.metric("Candidatos en el banco", len(banco))
    st.dataframe(vista, use_container_width=True)
    st.download_button(
        "Descargar banco (CSV)",
        banco.to_csv(index=False).encode("utf-8"),
        file_name="banco_candidatos.csv",
        mime="text/csv",
    )

    confirmo = st.checkbox("Confirmo que quiero vaciar el banco")
    if st.button("Vaciar banco") and confirmo:
        os.remove(ARCHIVO_BANCO)
        registrar_sesion("Banco de candidatos vaciado")
        st.rerun()
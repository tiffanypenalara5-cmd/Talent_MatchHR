"""Estimación del tiempo que tomaría contratar a cada candidato.

Son ESTIMACIONES basadas en supuestos que el reclutador puede editar (días hábiles y
horas de trabajo por etapa). No son datos reales de ninguna empresa."""

import io
import math
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from modulos.seguimiento import SIN_ESTADO

COLUMNAS_ETAPAS = ["Etapa", "Días hábiles", "Horas del reclutador"]

ETAPAS_BASE = [
    ("Revisión de CV y preselección", 1, 1.0),
    ("Coordinación de entrevistas", 2, 1.0),
    ("Entrevista(s) y evaluación", 3, 2.0),
    ("Pruebas técnicas o psicométricas", 3, 2.0),
    ("Verificación de referencias", 3, 1.0),
    ("Oferta y aceptación", 3, 1.0),
    ("Trámites de ingreso (contrato, afiliaciones)", 2, 1.5),
]

# Cuántas etapas ya se completaron según el estado registrado en «Seguimiento»
ETAPAS_COMPLETADAS = {SIN_ESTADO: 0, "Preseleccionado": 1, "Entrevista": 2}
MAX_DIAS = 60
MAX_HORAS = 200


def etapas_por_defecto():
    return pd.DataFrame(ETAPAS_BASE, columns=COLUMNAS_ETAPAS)


def _texto(valor):
    return "" if pd.isna(valor) else str(valor).strip()


def validar_etapas(tabla):
    """Convierte la tabla editada en una lista de etapas. Devuelve (etapas, errores)."""
    etapas, errores = [], []
    for n, (_, fila) in enumerate(tabla.iterrows(), start=1):
        nombre = _texto(fila.get("Etapa"))
        dias, horas = fila.get("Días hábiles"), fila.get("Horas del reclutador")
        if not nombre and pd.isna(dias) and pd.isna(horas):
            continue  # fila vacía
        if not nombre:
            errores.append(f"Fila {n}: falta el nombre de la etapa.")
            continue
        if pd.isna(dias) or pd.isna(horas):
            errores.append(f"«{nombre}»: falta el número de días o de horas.")
            continue
        try:
            dias, horas = float(dias), float(horas)
        except (TypeError, ValueError):
            errores.append(f"«{nombre}»: los días y las horas deben ser números.")
            continue
        if dias < 0 or horas < 0:
            errores.append(f"«{nombre}»: los días y las horas no pueden ser negativos.")
        elif dias > MAX_DIAS or horas > MAX_HORAS:
            errores.append(f"«{nombre}»: valor demasiado alto "
                           f"(máximo {MAX_DIAS} días y {MAX_HORAS} horas).")
        else:
            etapas.append({"nombre": nombre, "dias": dias, "horas": horas})
    if not etapas and not errores:
        errores.append("Debe haber al menos una etapa.")
    return etapas, errores


def _completadas(estado, etapas):
    if estado == "Contratado":
        return len(etapas)
    return min(ETAPAS_COMPLETADAS.get(estado, 0), len(etapas))


def calcular_tiempos(resultados, etapas, seguimiento, extra_dias, extra_horas, hoy=None):
    """Tabla con los días hábiles y las horas estimadas para cada candidato."""
    hoy = hoy or date.today()
    filas = []
    for r in resultados:
        candidato = r["candidato"]
        estado = seguimiento.get(candidato, {}).get("estado", SIN_ESTADO)
        n_sin = r["sin_evidencia"]
        base = {"Candidato": candidato, "Estado": estado, "Criterios sin evidencia": n_sin}

        if estado == "Descartado":
            filas.append({**base, "Etapas pendientes": None, "Días hábiles estimados": None,
                          "Horas del reclutador": None, "Fecha estimada de cierre": "No aplica"})
            continue

        pendientes = etapas[_completadas(estado, etapas):]
        dias = sum(e["dias"] for e in pendientes)
        horas = sum(e["horas"] for e in pendientes)
        if pendientes and n_sin > 0:
            dias += extra_dias
            horas += extra_horas * n_sin
        if pendientes:
            fecha = str(np.busday_offset(np.datetime64(hoy), int(math.ceil(dias)), roll="forward"))
        else:
            fecha = "Proceso completo"
        filas.append({**base, "Etapas pendientes": len(pendientes),
                      "Días hábiles estimados": round(dias, 1),
                      "Horas del reclutador": round(horas, 1),
                      "Fecha estimada de cierre": fecha})
    return pd.DataFrame(filas)


def desglose_candidato(estado, n_sin, etapas, extra_dias, extra_horas):
    """Tabla etapa por etapa para un candidato (hecha o pendiente)."""
    hechas = _completadas(estado, etapas)
    filas = [{"Etapa": e["nombre"], "Situación": "Hecha" if i < hechas else "Pendiente",
              "Días hábiles": e["dias"], "Horas": e["horas"]} for i, e in enumerate(etapas)]
    if n_sin > 0 and hechas < len(etapas):
        filas.append({"Etapa": f"Verificar {n_sin} criterio(s) sin evidencia",
                      "Situación": "Pendiente", "Días hábiles": extra_dias,
                      "Horas": round(extra_horas * n_sin, 1)})
    return pd.DataFrame(filas)


def tiempos_a_excel(tabla, etapas, extra_dias, extra_horas):
    supuestos = pd.DataFrame(
        [{"Etapa": e["nombre"], "Días hábiles": e["dias"], "Horas del reclutador": e["horas"]}
         for e in etapas]
        + [{"Etapa": "Extra por criterios sin evidencia (días, una vez)",
            "Días hábiles": extra_dias, "Horas del reclutador": None},
           {"Etapa": "Extra por cada criterio sin evidencia (horas)",
            "Días hábiles": None, "Horas del reclutador": extra_horas}])
    salida = io.BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as escritor:
        tabla.to_excel(escritor, sheet_name="Tiempos", index=False)
        supuestos.to_excel(escritor, sheet_name="Supuestos", index=False)
        for hoja in escritor.sheets.values():
            for columna in hoja.columns:
                ancho = max(len(str(c.value)) if c.value is not None else 0 for c in columna)
                hoja.column_dimensions[columna[0].column_letter].width = min(60, ancho + 2)
    return salida.getvalue()


def pestana_tiempos(resultados):
    """Pestaña 'Tiempo de contratación' de la pantalla Candidatos."""
    seguimiento = st.session_state.get("seguimiento", {})

    st.caption("Estimación de los días hábiles y las horas de trabajo que tomaría contratar a "
               "cada candidato, según las etapas que le faltan. Son supuestos que usted puede "
               "ajustar: no son datos reales de una empresa. Los feriados no se descuentan.")

    if "etapas_tiempo_base" not in st.session_state:
        st.session_state["etapas_tiempo_base"] = etapas_por_defecto()

    with st.expander("Ajustar la duración estimada de cada etapa"):
        tabla = st.data_editor(
            st.session_state["etapas_tiempo_base"],
            key="editor_etapas_tiempo",
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "Etapa": st.column_config.TextColumn("Etapa", required=True),
                "Días hábiles": st.column_config.NumberColumn("Días hábiles", min_value=0,
                                                              step=0.5, format="%g"),
                "Horas del reclutador": st.column_config.NumberColumn(
                    "Horas del reclutador", min_value=0, step=0.5, format="%g"),
            },
        )
        c1, c2 = st.columns(2)
        extra_dias = c1.number_input("Días extra si hay criterios sin evidencia",
                                     min_value=0.0, max_value=30.0, value=1.0, step=0.5,
                                     key="extra_dias_tiempo")
        extra_horas = c2.number_input("Horas por cada criterio sin evidencia",
                                      min_value=0.0, max_value=20.0, value=0.5, step=0.5,
                                      key="extra_horas_tiempo")

    etapas, errores = validar_etapas(tabla)
    if errores:
        st.error("Corrija lo siguiente en la tabla de etapas:")
        for e in errores:
            st.write("•", e)
        etapas = st.session_state.get("etapas_validas")
        if not etapas:
            etapas, _ = validar_etapas(etapas_por_defecto())
        st.info("Mientras tanto se usa la última versión válida.")
    else:
        st.session_state["etapas_validas"] = etapas

    tiempos = calcular_tiempos(resultados, etapas, seguimiento, extra_dias, extra_horas)
    activos = tiempos[tiempos["Días hábiles estimados"].notna()]

    if activos.empty:
        st.info("No hay candidatos en proceso: todos están descartados.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Candidatos en proceso", len(activos))
        m2.metric("Promedio de días hábiles", f"{activos['Días hábiles estimados'].mean():.1f}")
        m3.metric("Horas totales del reclutador", f"{activos['Horas del reclutador'].sum():.1f}")
        fechas = [f for f in activos["Fecha estimada de cierre"] if f != "Proceso completo"]
        m4.metric("Cierre más lejano", max(fechas) if fechas else "—")

    st.dataframe(tiempos, hide_index=True)

    if not activos.empty:
        st.subheader("Días hábiles estimados por candidato")
        st.bar_chart(activos.set_index("Candidato")[["Días hábiles estimados"]], color="#0F766E")

    st.subheader("Desglose de un candidato")
    elegido = st.selectbox("Candidato", [r["candidato"] for r in resultados],
                           key="tiempo_candidato")
    r = next(x for x in resultados if x["candidato"] == elegido)
    estado = seguimiento.get(elegido, {}).get("estado", SIN_ESTADO)
    if estado == "Descartado":
        st.info("Este candidato está descartado: no se estima su tiempo de contratación.")
    else:
        st.write(f"Estado actual: **{estado}**")
        st.dataframe(desglose_candidato(estado, r["sin_evidencia"], etapas, extra_dias,
                                        extra_horas), hide_index=True)

    st.download_button("Descargar estimación (.xlsx)",
                       data=tiempos_a_excel(tiempos, etapas, extra_dias, extra_horas),
                       file_name="tiempo_contratacion_talentmatch.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
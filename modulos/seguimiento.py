"""Seguimiento del proceso: estado y nota de cada candidato (preseleccionado, entrevista...)."""

import io
from datetime import datetime

import pandas as pd
import streamlit as st

from modulos.evaluador import generar_ranking
from modulos.modulo_proceso import registrar_sesion

SIN_ESTADO = "Sin estado"
ESTADOS = [SIN_ESTADO, "Preseleccionado", "Entrevista", "Descartado", "Contratado"]
COLUMNAS_BLOQUEADAS = ["Candidato", "Puntaje confirmado", "Puntaje posible", "Revisión manual"]


def _texto(valor):
    return "" if pd.isna(valor) else str(valor).strip()


def actualizar_seguimiento(seguimiento, editado, hoy=None):
    """Guarda en 'seguimiento' los estados y notas de la tabla editada.
    Devuelve cuántos candidatos cambiaron de estado o de nota."""
    hoy = hoy or datetime.now().strftime("%Y-%m-%d")
    cambios = 0
    for _, fila in editado.iterrows():
        candidato = _texto(fila["Candidato"])
        estado = _texto(fila["Estado"]) or SIN_ESTADO
        if estado not in ESTADOS:
            estado = SIN_ESTADO
        nota = _texto(fila["Nota"])[:200]

        anterior = seguimiento.get(candidato)
        if anterior is None:
            if estado == SIN_ESTADO and not nota:
                continue  # no hay nada que guardar
            seguimiento[candidato] = {"estado": estado, "nota": nota, "fecha_estado": hoy}
            cambios += 1
        elif anterior["estado"] != estado or anterior["nota"] != nota:
            fecha = hoy if anterior["estado"] != estado else anterior["fecha_estado"]
            seguimiento[candidato] = {"estado": estado, "nota": nota, "fecha_estado": fecha}
            cambios += 1
    return cambios


def tabla_para_descargar(editado, seguimiento):
    """Tabla del seguimiento con la fecha del último cambio de estado."""
    tabla = editado.copy()
    tabla["Fecha del estado"] = [
        seguimiento.get(_texto(c), {}).get("fecha_estado", "") for c in tabla["Candidato"]]
    return tabla


def seguimiento_a_excel(tabla):
    salida = io.BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as escritor:
        tabla.to_excel(escritor, sheet_name="Seguimiento", index=False)
        hoja = escritor.sheets["Seguimiento"]
        for columna in hoja.columns:
            ancho = max(len(str(c.value)) if c.value is not None else 0 for c in columna)
            hoja.column_dimensions[columna[0].column_letter].width = min(60, ancho + 2)
    return salida.getvalue()


def pestana_seguimiento(resultados):
    """Pestaña 'Seguimiento del proceso' de la pantalla Candidatos."""
    seguimiento = st.session_state.setdefault("seguimiento", {})
    ranking = generar_ranking(resultados)
    sin_evidencia = {r["candidato"]: r["sin_evidencia"] for r in resultados}

    st.caption("Registre en qué etapa va cada candidato. La decisión es suya: el programa "
               "solo la registra. Los cambios se mantienen mientras la sesión esté abierta; "
               "descargue el seguimiento para conservarlo.")

    base = pd.DataFrame([{
        "Candidato": f["Candidato"],
        "Puntaje confirmado": f["Puntaje confirmado"],
        "Puntaje posible": f["Puntaje posible"],
        "Revisión manual": "Sí" if sin_evidencia[f["Candidato"]] > 0 else "No",
        "Estado": seguimiento.get(f["Candidato"], {}).get("estado", SIN_ESTADO),
        "Nota": seguimiento.get(f["Candidato"], {}).get("nota", ""),
    } for _, f in ranking.iterrows()])

    clave = "editor_seguimiento_" + str(abs(hash(tuple(base["Candidato"]))))
    editado = st.data_editor(
        base,
        key=clave,
        hide_index=True,
        disabled=COLUMNAS_BLOQUEADAS,
        column_config={
            "Estado": st.column_config.SelectboxColumn("Estado", options=ESTADOS, required=True),
            "Nota": st.column_config.TextColumn("Nota", max_chars=200),
        },
    )

    cambios = actualizar_seguimiento(seguimiento, editado)
    if cambios:
        try:
            registrar_sesion(f"Seguimiento actualizado: {cambios} cambio(s)")
        except OSError:
            pass

    conteo = {e: sum(1 for v in seguimiento.values() if v["estado"] == e) for e in ESTADOS[1:]}
    columnas = st.columns(len(conteo))
    for columna, (estado, cantidad) in zip(columnas, conteo.items()):
        columna.metric(estado, cantidad)

    riesgo = [c for c, v in seguimiento.items()
              if v["estado"] == "Descartado" and sin_evidencia.get(c, 0) > 0]
    if riesgo:
        st.warning("Hay candidatos descartados con criterios sin evidencia: "
                   + ", ".join(riesgo) + ". Verifique esa información antes de cerrar la decisión.")

    tabla = tabla_para_descargar(editado, seguimiento)
    st.download_button("Descargar seguimiento (.xlsx)", data=seguimiento_a_excel(tabla),
                       file_name="seguimiento_talentmatch.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
"""Plantillas y archivos de vacantes: cargar plantillas listas, guardar y reabrir vacantes."""

import json
import re

import streamlit as st

from modulos.conversiones import vacante_ejemplo, vacante_a_tabla
from modulos.modulo_proceso import registrar_sesion
from modulos.vacantes import Criterio, Vacante, validar_vacante

FORMATO = "talentmatch-vacante"
MAX_BYTES = 200_000


class ErrorPlantilla(Exception):
    """Problema al leer un archivo de vacante. El mensaje se puede mostrar al usuario."""


def _asistente_administrativo():
    return Vacante(
        nombre="Asistente Administrativo",
        descripcion="Apoyo administrativo, atención al público y manejo de documentos.",
        criterios=[
            Criterio("Experiencia administrativa", "Experiencia", 35, minimo=1),
            Criterio("Herramientas ofimáticas", "Competencias técnicas", 25,
                     ["excel", "word", "outlook"]),
            Criterio("Formación afín", "Formación académica", 15,
                     ["administración", "secretariado", "gestión administrativa", "contabilidad"]),
            Criterio("Atención al cliente", "Conocimientos específicos", 15,
                     ["atención al cliente", "servicio al cliente"]),
            Criterio("Inglés", "Idiomas", 10, ["inglés"]),
        ],
    )


def _reclutador():
    return Vacante(
        nombre="Reclutador/a de Personal",
        descripcion="Reclutamiento, preselección y entrevistas de candidatos.",
        criterios=[
            Criterio("Experiencia en reclutamiento", "Experiencia", 35, minimo=2),
            Criterio("Reclutamiento y selección", "Competencias técnicas", 25,
                     ["reclutamiento", "selección de personal", "entrevistas"]),
            Criterio("Formación afín", "Formación académica", 15,
                     ["recursos humanos", "psicología", "administración"]),
            Criterio("Legislación laboral", "Conocimientos específicos", 15,
                     ["código de trabajo", "legislación laboral"]),
            Criterio("Inglés", "Idiomas", 10, ["inglés"]),
        ],
    )


def _operativo():
    return Vacante(
        nombre="Puesto Operativo",
        descripcion="Puestos de planta, bodega o servicios: se valora sobre todo la experiencia.",
        criterios=[
            Criterio("Experiencia en puestos similares", "Experiencia", 50, minimo=1),
            Criterio("Manejo de equipo o herramientas", "Competencias técnicas", 20,
                     ["herramientas", "equipo", "maquinaria", "montacargas", "bodega"]),
            Criterio("Escolaridad", "Formación académica", 15,
                     ["primaria", "secundaria", "bachillerato", "colegio"]),
            Criterio("Cursos o licencias", "Conocimientos específicos", 15,
                     ["licencia", "curso", "certificado", "capacitación"]),
        ],
    )


PLANTILLAS = {
    "Analista de Recursos Humanos": vacante_ejemplo,
    "Asistente Administrativo": _asistente_administrativo,
    "Reclutador/a de Personal": _reclutador,
    "Puesto Operativo": _operativo,
}


def vacante_a_json(vacante):
    """Convierte una Vacante en el contenido de un archivo .json (bytes)."""
    datos = {
        "formato": FORMATO,
        "version": 1,
        "nombre": vacante.nombre,
        "descripcion": vacante.descripcion,
        "criterios": [{
            "nombre": c.nombre,
            "categoria": c.categoria,
            "peso": c.peso,
            "palabras_clave": list(c.palabras_clave),
            "minimo": c.minimo,
        } for c in vacante.criterios],
    }
    return json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8")


def json_a_vacante(contenido):
    """Lee el contenido de un archivo .json y devuelve una Vacante válida.
    Si algo está mal, lanza ErrorPlantilla con un mensaje claro."""
    if len(contenido) > MAX_BYTES:
        raise ErrorPlantilla("El archivo es demasiado grande para ser una vacante.")
    try:
        datos = json.loads(contenido.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ErrorPlantilla("El archivo no es un JSON válido o está dañado.") from None

    if not isinstance(datos, dict) or datos.get("formato") != FORMATO:
        raise ErrorPlantilla("El archivo no tiene el formato de una vacante de TalentMatch HR.")

    criterios = []
    try:
        for c in datos["criterios"]:
            criterios.append(Criterio(
                nombre=str(c["nombre"]),
                categoria=str(c["categoria"]),
                peso=float(c["peso"]),
                palabras_clave=[str(p) for p in c.get("palabras_clave", [])],
                minimo=float(c.get("minimo", 0)),
            ))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ErrorPlantilla("Un criterio del archivo está incompleto o tiene datos inválidos.") from None

    vacante = Vacante(nombre=str(datos.get("nombre", "")),
                      descripcion=str(datos.get("descripcion", "")),
                      criterios=criterios)
    errores = validar_vacante(vacante)
    if errores:
        raise ErrorPlantilla("La vacante del archivo no es válida: " + " ".join(errores))
    return vacante


def aplicar_vacante(vacante):
    """Pone una vacante en la pantalla (tabla, nombre y descripción)."""
    st.session_state["vacante"] = vacante
    st.session_state["tabla_inicial"] = vacante_a_tabla(vacante)
    st.session_state["nombre_vacante"] = vacante.nombre
    st.session_state["descripcion_vacante"] = vacante.descripcion
    st.session_state.pop("editor_criterios", None)  # reinicia la tabla editable


def _registrar(accion):
    try:
        registrar_sesion(accion)
    except OSError:
        pass  # si no se puede escribir el registro, el programa sigue funcionando


def _mensaje(tipo, texto):
    st.session_state["mensaje_plantilla"] = (tipo, texto)


def _cargar_plantilla():
    nombre = st.session_state["plantilla_elegida"]
    aplicar_vacante(PLANTILLAS[nombre]())
    _registrar(f"Plantilla de vacante cargada: {nombre}")
    _mensaje("ok", f"Plantilla «{nombre}» cargada.")


def _cargar_archivo():
    archivo = st.session_state.get("archivo_vacante")
    if archivo is None:
        _mensaje("error", "Primero seleccione un archivo .json.")
        return
    try:
        vacante = json_a_vacante(archivo.getvalue())
    except ErrorPlantilla as error:
        _mensaje("error", str(error))
        return
    aplicar_vacante(vacante)
    _registrar(f"Vacante cargada desde archivo: {vacante.nombre}")
    _mensaje("ok", f"Vacante «{vacante.nombre}» cargada desde el archivo.")


def panel_plantillas():
    """Panel desplegable con plantillas, carga y descarga de vacantes."""
    with st.expander("Plantillas y archivos de vacante"):
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("Plantilla lista para usar", list(PLANTILLAS), key="plantilla_elegida")
            st.button("Cargar plantilla", on_click=_cargar_plantilla)
        with c2:
            st.file_uploader("Cargar una vacante guardada (.json)", type=["json"],
                             key="archivo_vacante")
            st.button("Cargar archivo", on_click=_cargar_archivo)

        mensaje = st.session_state.pop("mensaje_plantilla", None)
        if mensaje:
            (st.success if mensaje[0] == "ok" else st.error)(mensaje[1])

        vacante = st.session_state["vacante"]
        nombre_seguro = re.sub(r"[^\w\-]", "_", vacante.nombre) or "vacante"
        st.download_button("Guardar esta vacante (.json)",
                           data=vacante_a_json(vacante),
                           file_name=f"vacante_{nombre_seguro}.json",
                           mime="application/json")
        st.caption("Se guarda la última versión válida de la vacante. Con el archivo "
                   "puede volver a cargarla en otra sesión o en otro computador.")
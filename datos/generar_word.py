"""Genera 3 archivos Word FICTICIOS para probar la lectura de CV en .docx.

Ejecutar desde la carpeta del proyecto:  python -m datos.generar_word
Todos los datos son inventados.
"""

import os

from docx import Document

CARPETA = "datos/cvs_word_ejemplo"


def _cv_normal():
    """CV con títulos y párrafos, como un documento de Word común."""
    doc = Document()
    doc.add_heading("CANDIDATA FICTICIA W01", level=1)
    doc.add_paragraph("Correo: ficticiaw01@ejemplo.com")
    secciones = [
        ("FORMACION ACADEMICA", ["Licenciatura en Administración de Recursos Humanos"]),
        ("EXPERIENCIA LABORAL", ["Analista de personal, 2018 - 2024"]),
        ("COMPETENCIAS TECNICAS", ["Excel avanzado, reclutamiento"]),
        ("IDIOMAS", ["Inglés B2"]),
        ("CONOCIMIENTOS ESPECIFICOS", ["Código de Trabajo"]),
    ]
    for titulo, lineas in secciones:
        doc.add_heading(titulo, level=2)
        for linea in lineas:
            doc.add_paragraph(linea)
    return doc


def _cv_con_tabla():
    """CV con el diseño en una tabla de dos columnas (muy común en plantillas de Word)."""
    doc = Document()
    doc.add_heading("CANDIDATO FICTICIO W02", level=1)
    filas = [
        ("FORMACION ACADEMICA", "Técnico en Gestión Administrativa"),
        ("EXPERIENCIA LABORAL", "Auxiliar administrativo, 2 años"),
        ("COMPETENCIAS TECNICAS", "Excel, Word"),
        ("CONOCIMIENTOS ESPECIFICOS", "Atención al cliente"),
    ]
    tabla = doc.add_table(rows=0, cols=2)
    for izquierda, derecha in filas:
        celdas = tabla.add_row().cells
        celdas[0].text = izquierda
        celdas[1].text = derecha
    return doc


def generar():
    os.makedirs(CARPETA, exist_ok=True)
    _cv_normal().save(os.path.join(CARPETA, "cv_word_01.docx"))
    _cv_con_tabla().save(os.path.join(CARPETA, "cv_word_02.docx"))
    # Archivo defectuoso: tiene extensión .docx pero no es un Word real
    with open(os.path.join(CARPETA, "cv_word_error.docx"), "wb") as f:
        f.write(b"Este archivo no es un documento de Word real.")
    print(f"Listo: 2 CV en Word + 1 archivo defectuoso en {CARPETA}")


if __name__ == "__main__":
    generar()
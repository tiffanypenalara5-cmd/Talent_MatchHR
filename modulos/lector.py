"""Lector de currículums: elige cómo leer cada archivo según su formato (PDF o Word)."""

import io
import os
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from modulos.lector_pdf import extraer_texto, ErrorLecturaPDF, MIN_CARACTERES

MAX_DESCOMPRIMIDO = 50 * 1024 * 1024  # protección contra archivos .docx "inflados"


def extraer_texto_word(contenido):
    """Lee un archivo .docx (en bytes) y devuelve su texto, en el orden en que aparece.
    Incluye el texto de las tablas, porque muchos CV en Word usan tablas para el diseño."""
    if len(contenido) == 0:
        raise ErrorLecturaPDF("El archivo está vacío.")
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as comprimido:
            if sum(info.file_size for info in comprimido.infolist()) > MAX_DESCOMPRIMIDO:
                raise ErrorLecturaPDF("El archivo Word es demasiado grande.")
        doc = Document(io.BytesIO(contenido))
    except ErrorLecturaPDF:
        raise
    except Exception:
        raise ErrorLecturaPDF(
            "El archivo no es un documento de Word (.docx) válido o está dañado.") from None

    lineas = []
    for hijo in doc.element.body.iterchildren():
        if hijo.tag.endswith("}p"):
            lineas.extend(Paragraph(hijo, doc).text.splitlines())
        elif hijo.tag.endswith("}tbl"):
            for fila in Table(hijo, doc).rows:
                vistas = []
                for celda in fila.cells:
                    if any(celda._tc is v for v in vistas):
                        continue  # celda combinada: ya se leyó
                    vistas.append(celda._tc)
                    lineas.extend(celda.text.splitlines())

    texto = "\n".join(linea for linea in lineas if linea.strip()).strip()
    if len(texto) < MIN_CARACTERES:
        raise ErrorLecturaPDF(
            "El documento de Word no contiene texto legible. Revise este CV manualmente.")
    return texto


def extraer_texto_archivo(nombre, contenido):
    """Recibe el nombre del archivo y su contenido (bytes). Devuelve {'texto': ...}.
    Si el archivo no se puede leer, lanza ErrorLecturaPDF con un mensaje claro."""
    extension = os.path.splitext(nombre)[1].lower()
    if extension == ".pdf":
        return extraer_texto(contenido)
    if extension == ".docx":
        return {"texto": extraer_texto_word(contenido), "paginas": None}
    if extension == ".doc":
        raise ErrorLecturaPDF("Los archivos .doc (Word antiguo) no se pueden leer. "
                              "Guárdelo como .docx o PDF.")
    raise ErrorLecturaPDF(f"Formato no compatible ({extension or 'sin extensión'}). "
                          "Use PDF o Word (.docx).")
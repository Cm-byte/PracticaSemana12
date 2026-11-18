"""Utilidades de sanitización de entrada."""
import re
import unicodedata

from django.utils.html import escape, strip_tags

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ESPACIOS = re.compile(r"[ \t]+")


def sanitize_input(valor, *, lower=False, escapar=False):
    """
    Limpia texto antes de validarlo/persistirlo:
      1. strip(): quita espacios al inicio y final.
      2. Normaliza Unicode (NFC) y elimina caracteres de control.
      3. strip_tags(): elimina etiquetas HTML.
      4. Colapsa espacios repetidos.
      5. lower() opcional (emails, usuarios).
      6. escape() opcional: convierte < > & " ' en entidades.
         Por defecto NO se escapa al guardar porque las plantillas de Django
         ya escapan al renderizar (autoescape) y se evitaría doble escape.
    """
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFC", str(valor)).strip()
    texto = _CONTROL.sub("", texto)
    texto = strip_tags(texto)
    texto = _ESPACIOS.sub(" ", texto)
    if lower:
        texto = texto.lower()
    if escapar:
        texto = escape(texto)
    return texto

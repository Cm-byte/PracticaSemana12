"""
Validadores personalizados reutilizables (nivel campo).
Se usan tanto en los modelos como en los formularios.
"""
import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# Celular peruano: 9 dígitos y empieza en 9 (ej. 987654321)
telefono_peru_validator = RegexValidator(
    regex=r"^9\d{8}$",
    message="Ingresa un celular peruano válido de 9 dígitos que empiece con 9.",
    code="telefono_invalido",
)

# Nombres de personas: letras (con tildes/ñ), espacios, apóstrofo y guion
nombre_persona_validator = RegexValidator(
    regex=r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü' -]{3,80}$",
    message="El nombre sólo puede contener letras y espacios (3 a 80 caracteres).",
    code="nombre_invalido",
)

PATRON_HTML = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
PATRON_SQL = re.compile(
    r"(\bunion\b\s+\bselect\b|\bdrop\b\s+\btable\b|\bdelete\b\s+\bfrom\b|\binsert\b\s+\binto\b|'\s*or\s+'?1'?\s*=\s*'?1|--\s|/\*|\*/|;\s*(drop|delete|update|insert)\b)",
    re.IGNORECASE,
)
PATRON_SCRIPT = re.compile(r"(javascript:|on\w+\s*=)", re.IGNORECASE)


def validar_sin_html(valor):
    """Rechaza etiquetas HTML o JavaScript embebido (prevención de XSS almacenado)."""
    if valor and (PATRON_HTML.search(valor) or PATRON_SCRIPT.search(valor)):
        raise ValidationError(
            "No se permiten etiquetas HTML ni código JavaScript.", code="contiene_html"
        )


def validar_sin_sql(valor):
    """
    Defensa en profundidad: el ORM ya parametriza las consultas (evita SQLi),
    pero rechazamos patrones típicos de inyección en campos de texto libre.
    """
    if valor and PATRON_SQL.search(valor):
        raise ValidationError(
            "El texto contiene secuencias no permitidas.", code="patron_sospechoso"
        )


def validar_url_unsplash(valor):
    """Las imágenes se cargan por enlace y la CSP sólo permite images.unsplash.com."""
    if valor and not valor.startswith("https://images.unsplash.com/"):
        raise ValidationError(
            "La imagen debe ser un enlace https://images.unsplash.com/...", code="url_no_permitida"
        )

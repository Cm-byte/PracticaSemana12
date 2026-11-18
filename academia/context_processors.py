def datos_escuela(request):
    """Datos disponibles en todas las plantillas."""
    es_instructor = request.user.is_authenticated and request.user.has_perm("academia.add_curso")
    return {
        "ESCUELA": {
            "nombre": "TejeArte",
            "lema": "Escuela de tejido a palitos, crochet y telar",
            "direccion": "Jr. Ancash 450, Huancayo",
            "telefono": "964 123 456",
        },
        "es_instructor": es_instructor,
    }

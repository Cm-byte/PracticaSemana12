import csv

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import Categoria, Curso, Inscripcion, MensajeContacto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "icono", "total_cursos")
    search_fields = ("nombre",)
    prepopulated_fields = {"slug": ("nombre",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total=Count("cursos"))

    @admin.display(description="N.° cursos", ordering="_total")
    def total_cursos(self, obj):
        return obj._total


class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 0
    fields = ("alumno", "telefono", "experiencia", "estado", "fecha_inscripcion")
    readonly_fields = ("alumno", "telefono", "experiencia", "fecha_inscripcion")
    can_delete = False
    show_change_link = True


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre", "categoria", "nivel", "modalidad", "instructor",
        "precio_soles", "cupos", "cupos_libres", "fecha_inicio", "estado",
    )
    list_display_links = ("nombre",)
    list_filter = ("activo", "nivel", "modalidad", "categoria", "fecha_inicio")
    search_fields = ("nombre", "descripcion", "instructor__username", "instructor__first_name")
    list_select_related = ("categoria", "instructor")  # evita N+1 consultas
    readonly_fields = ("vista_previa", "creado", "actualizado", "cupos_libres")
    prepopulated_fields = {"slug": ("nombre",)}
    date_hierarchy = "fecha_inicio"
    list_per_page = 15
    autocomplete_fields = ("categoria",)
    inlines = [InscripcionInline]
    actions = ["publicar", "despublicar", "exportar_csv"]
    fieldsets = (
        ("Datos del curso", {"fields": ("nombre", "slug", "categoria", "instructor", "nivel", "modalidad", "descripcion")}),
        ("Imagen (por enlace)", {"fields": ("imagen_url", "vista_previa")}),
        ("Programación y costo", {"fields": (("fecha_inicio", "fecha_fin"), "horario", ("precio", "cupos", "cupos_libres"), "activo")}),
        ("Auditoría", {"classes": ("collapse",), "fields": ("creado", "actualizado")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _inscritos=Count("inscripciones", filter=~Q(inscripciones__estado="cancelada"))
        )

    # ---- Campos calculados ----
    @admin.display(description="Precio", ordering="precio")
    def precio_soles(self, obj):
        return f"S/ {obj.precio:,.2f}"

    @admin.display(description="Cupos libres")
    def cupos_libres(self, obj):
        inscritos = getattr(obj, "_inscritos", None)
        if inscritos is None:
            inscritos = obj.inscritos
        libres = max(obj.cupos - inscritos, 0)
        color = "#2e7d32" if libres > 3 else ("#ef6c00" if libres > 0 else "#c62828")
        return format_html('<b style="color:{}">{}</b> / {}', color, libres, obj.cupos)

    @admin.display(description="Estado", boolean=True, ordering="activo")
    def estado(self, obj):
        return obj.activo

    @admin.display(description="Vista previa")
    def vista_previa(self, obj):
        if not obj.imagen_url:
            return "—"
        return format_html('<img src="{}" style="max-height:140px;border-radius:8px" alt="{}">', obj.imagen_url, obj.nombre)

    # ---- Acciones masivas: reciben (self, request, queryset) ----
    @admin.action(description="Publicar cursos seleccionados", permissions=["publicar"])
    def publicar(self, request, queryset):
        n = queryset.update(activo=True)
        self.message_user(request, f"{n} curso(s) publicados.", messages.SUCCESS)

    @admin.action(description="Despublicar cursos seleccionados", permissions=["publicar"])
    def despublicar(self, request, queryset):
        n = queryset.update(activo=False)
        self.message_user(request, f"{n} curso(s) despublicados.", messages.WARNING)

    def has_publicar_permission(self, request):
        return request.user.has_perm("academia.publicar_curso")

    @admin.action(description="Exportar a CSV")
    def exportar_csv(self, request, queryset):
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="cursos_{timezone.now():%Y%m%d}.csv"'
        respuesta.write("﻿")  # BOM para Excel
        w = csv.writer(respuesta)
        w.writerow(["Curso", "Categoría", "Nivel", "Precio", "Cupos", "Inicio", "Publicado"])
        for c in queryset.select_related("categoria"):
            w.writerow([c.nombre, c.categoria, c.get_nivel_display(), c.precio, c.cupos, c.fecha_inicio, c.activo])
        return respuesta


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("alumno_nombre", "curso", "nivel_curso", "telefono", "experiencia", "estado_color", "fecha_inscripcion")
    list_filter = ("estado", "curso__nivel", "curso", "fecha_inscripcion")
    search_fields = ("alumno__username", "alumno__first_name", "alumno__last_name", "alumno__email", "curso__nombre", "telefono")
    list_select_related = ("alumno", "curso")
    readonly_fields = ("fecha_inscripcion",)
    autocomplete_fields = ("curso",)
    raw_id_fields = ("alumno",)
    actions = ["confirmar", "cancelar"]
    date_hierarchy = "fecha_inscripcion"

    @admin.display(description="Alumna(o)", ordering="alumno__first_name")
    def alumno_nombre(self, obj):
        return obj.alumno.get_full_name() or obj.alumno.username

    @admin.display(description="Nivel", ordering="curso__nivel")
    def nivel_curso(self, obj):
        return obj.curso.get_nivel_display()

    @admin.display(description="Estado", ordering="estado")
    def estado_color(self, obj):
        colores = {"pendiente": "#ef6c00", "confirmada": "#2e7d32", "cancelada": "#9e9e9e"}
        return format_html('<span style="color:{};font-weight:600">{}</span>', colores[obj.estado], obj.get_estado_display())

    @admin.action(description="Confirmar inscripciones seleccionadas")
    def confirmar(self, request, queryset):
        n = queryset.exclude(estado="cancelada").update(estado="confirmada")
        self.message_user(request, f"{n} inscripción(es) confirmadas.", messages.SUCCESS)

    @admin.action(description="Cancelar inscripciones seleccionadas")
    def cancelar(self, request, queryset):
        n = queryset.update(estado="cancelada")
        self.message_user(request, f"{n} inscripción(es) canceladas.", messages.WARNING)


@admin.register(MensajeContacto)
class MensajeContactoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "email", "asunto", "atendido", "creado")
    list_filter = ("atendido", "asunto", "creado")
    search_fields = ("nombre", "email", "mensaje")
    list_editable = ("atendido",)
    readonly_fields = ("nombre", "email", "telefono", "asunto", "mensaje", "creado")
    actions = ["marcar_atendido"]

    def has_add_permission(self, request):
        return False  # los mensajes sólo llegan desde el formulario público

    @admin.action(description="Marcar como atendidos")
    def marcar_atendido(self, request, queryset):
        n = queryset.update(atendido=True)
        self.message_user(request, f"{n} mensaje(s) marcados como atendidos.")

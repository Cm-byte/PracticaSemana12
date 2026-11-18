from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from .validators import telefono_peru_validator, validar_sin_html, validar_url_unsplash


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)
    descripcion = models.CharField("descripción", max_length=200, blank=True, validators=[validar_sin_html])
    icono = models.CharField(
        max_length=40, default="bi-flower1", help_text="Clase de Bootstrap Icons, ej. bi-flower1"
    )

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Curso(models.Model):
    class Nivel(models.TextChoices):
        BASICO = "basico", "Básico"
        INTERMEDIO = "intermedio", "Intermedio"
        AVANZADO = "avanzado", "Avanzado"

    class Modalidad(models.TextChoices):
        PRESENCIAL = "presencial", "Presencial"
        VIRTUAL = "virtual", "Virtual"

    nombre = models.CharField(max_length=120, unique=True, validators=[validar_sin_html])
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="cursos", verbose_name="categoría")
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cursos_dictados",
        limit_choices_to={"groups__name": "Instructores"},
    )
    nivel = models.CharField(max_length=12, choices=Nivel.choices, default=Nivel.BASICO)
    modalidad = models.CharField(max_length=12, choices=Modalidad.choices, default=Modalidad.PRESENCIAL)
    descripcion = models.TextField("descripción", validators=[validar_sin_html])
    imagen_url = models.URLField(
        "imagen (enlace)", max_length=400, validators=[validar_url_unsplash],
        help_text="Enlace https://images.unsplash.com/... (las imágenes no se suben, se enlazan)",
    )
    precio = models.DecimalField(
        max_digits=7, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    cupos = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(40)])
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    horario = models.CharField(max_length=80, help_text="Ej. Sábados 9:00 – 12:00")
    activo = models.BooleanField("publicado", default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fecha_inicio", "nombre"]
        permissions = [("publicar_curso", "Puede publicar o despublicar cursos")]

    def __str__(self):
        return self.nombre

    # Validación de nivel MODELO (3er nivel): se ejecuta con full_clean(),
    # que ModelForm invoca automáticamente en is_valid().
    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha de fin no puede ser anterior al inicio."})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)[:140]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("academia:curso_detalle", args=[self.slug])

    @property
    def inscritos(self):
        return self.inscripciones.exclude(estado=Inscripcion.Estado.CANCELADA).count()

    @property
    def cupos_disponibles(self):
        return max(self.cupos - self.inscritos, 0)


class Inscripcion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        CONFIRMADA = "confirmada", "Confirmada"
        CANCELADA = "cancelada", "Cancelada"

    class Experiencia(models.TextChoices):
        NINGUNA = "ninguna", "Nunca he tejido"
        BASICA = "basica", "Sé puntos básicos"
        MEDIA = "media", "Tejo prendas sencillas"
        ALTA = "alta", "Tejo con patrones complejos"

    alumno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inscripciones")
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="inscripciones")
    telefono = models.CharField("teléfono", max_length=9, validators=[telefono_peru_validator])
    experiencia = models.CharField(max_length=10, choices=Experiencia.choices, default=Experiencia.NINGUNA)
    comentario = models.TextField(blank=True, validators=[validar_sin_html])
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_inscripcion = models.DateTimeField("fecha de inscripción", auto_now_add=True)

    class Meta:
        verbose_name = "inscripción"
        verbose_name_plural = "inscripciones"
        ordering = ["-fecha_inscripcion"]
        constraints = [
            models.UniqueConstraint(fields=["alumno", "curso"], name="inscripcion_unica_por_curso"),
        ]

    def __str__(self):
        return f"{self.alumno} → {self.curso}"


class MensajeContacto(models.Model):
    class Asunto(models.TextChoices):
        INFORMES = "informes", "Informes generales"
        INSCRIPCION = "inscripcion", "Ayuda con inscripción"
        TALLER = "taller", "Taller para empresas/colegios"
        OTRO = "otro", "Otro"

    nombre = models.CharField(max_length=80)
    email = models.EmailField()
    telefono = models.CharField(max_length=9, blank=True)
    asunto = models.CharField(max_length=12, choices=Asunto.choices)
    mensaje = models.TextField()
    atendido = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "mensaje de contacto"
        verbose_name_plural = "mensajes de contacto"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} – {self.get_asunto_display()}"

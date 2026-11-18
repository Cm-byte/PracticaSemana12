"""
Formularios de TejeArte.

Ciclo de vida: Form(request.POST) -> is_valid() -> [to_python -> validators
-> clean_<campo>()] por cada campo -> clean() (cross-field) -> [ModelForm:
instance.full_clean() -> Model.clean()] -> cleaned_data -> save().
"""
from datetime import date

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Curso, Inscripcion, MensajeContacto
from .utils import sanitize_input
from .validators import (
    nombre_persona_validator,
    telefono_peru_validator,
    validar_sin_html,
    validar_sin_sql,
)


class BootstrapMixin:
    """Agrega clases de Bootstrap a todos los widgets (presentación separada de la lógica)."""

    def _aplicar_bootstrap(self):
        for nombre, campo in self.fields.items():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                clase = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                clase = "form-select"
            else:
                clase = "form-control"
            if self.is_bound and nombre in self.errors:
                clase += " is-invalid"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {clase}".strip()

    def full_clean(self):
        super().full_clean()
        self._aplicar_bootstrap()  # re-aplica para marcar is-invalid tras validar


# ---------------------------------------------------------------------------
# 1) FORMULARIO CLÁSICO (forms.Form) – Contacto
# ---------------------------------------------------------------------------
class ContactoForm(BootstrapMixin, forms.Form):
    nombre = forms.CharField(
        label="Nombre completo", max_length=80, validators=[nombre_persona_validator],
        widget=forms.TextInput(attrs={"placeholder": "Ej. María Quispe"}),
    )
    email = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"placeholder": "tucorreo@ejemplo.com"}))
    telefono = forms.CharField(
        label="Celular", max_length=9, required=False, validators=[telefono_peru_validator],
        widget=forms.TextInput(attrs={"placeholder": "987654321", "inputmode": "numeric"}),
        help_text="Obligatorio si tu consulta es sobre inscripción.",
    )
    asunto = forms.ChoiceField(label="Asunto", choices=MensajeContacto.Asunto.choices)
    mensaje = forms.CharField(
        label="Mensaje", min_length=20, max_length=1000,
        validators=[validar_sin_html, validar_sin_sql],
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Cuéntanos qué te gustaría aprender..."}),
    )
    acepta_politica = forms.BooleanField(label="Acepto el tratamiento de mis datos personales (Ley N.° 29733)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    # --- Nivel 1: validación por campo -----------------------------------
    def clean_nombre(self):
        nombre = sanitize_input(self.cleaned_data["nombre"])
        return nombre.title()

    def clean_email(self):
        email = sanitize_input(self.cleaned_data["email"], lower=True)
        if email.endswith(("@mailinator.com", "@yopmail.com")):
            raise ValidationError("No se aceptan correos temporales.", code="email_temporal")
        return email

    def clean_mensaje(self):
        mensaje = sanitize_input(self.cleaned_data["mensaje"])
        if len(mensaje) < 20:
            raise ValidationError("El mensaje debe tener al menos 20 caracteres útiles.")
        return mensaje

    # --- Nivel 2: validación cross-field ---------------------------------
    def clean(self):
        datos = super().clean()
        asunto = datos.get("asunto")
        telefono = datos.get("telefono")
        if asunto == MensajeContacto.Asunto.INSCRIPCION and not telefono:
            # Error NO fatal asociado a un campo concreto
            self.add_error("telefono", "Déjanos tu celular para ayudarte con la inscripción.")
        nombre = (datos.get("nombre") or "").lower()
        mensaje = (datos.get("mensaje") or "").lower()
        if nombre and mensaje and mensaje.count("http") > 2:
            # Error global (__all__) -> form.non_field_errors
            raise ValidationError("El mensaje parece spam (demasiados enlaces).", code="spam")
        return datos

    def guardar(self):
        return MensajeContacto.objects.create(
            nombre=self.cleaned_data["nombre"],
            email=self.cleaned_data["email"],
            telefono=self.cleaned_data.get("telefono", ""),
            asunto=self.cleaned_data["asunto"],
            mensaje=self.cleaned_data["mensaje"],
        )


# ---------------------------------------------------------------------------
# 2) MODELFORM – Inscripción a un curso
# ---------------------------------------------------------------------------
class InscripcionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Inscripcion
        fields = ["curso", "telefono", "experiencia", "comentario"]
        labels = {
            "curso": "Curso",
            "telefono": "Celular",
            "experiencia": "Tu experiencia tejiendo",
            "comentario": "¿Algo que debamos saber? (opcional)",
        }
        widgets = {"comentario": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, alumno=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.alumno = alumno
        self.fields["curso"].queryset = Curso.objects.filter(activo=True, fecha_inicio__gte=date.today()).select_related("categoria")
        self.fields["curso"].empty_label = "— Selecciona un curso —"
        self._aplicar_bootstrap()

    def clean_telefono(self):
        return sanitize_input(self.cleaned_data["telefono"]).replace(" ", "")

    def clean_comentario(self):
        return sanitize_input(self.cleaned_data.get("comentario", ""))

    def clean(self):
        datos = super().clean()
        curso = datos.get("curso")
        experiencia = datos.get("experiencia")
        if not curso:
            return datos
        if curso.nivel == Curso.Nivel.AVANZADO and experiencia in (
            Inscripcion.Experiencia.NINGUNA, Inscripcion.Experiencia.BASICA,
        ):
            self.add_error(
                "experiencia",
                "Para un curso avanzado necesitas experiencia previa. Te recomendamos empezar por el nivel básico o intermedio.",
            )
        if curso.cupos_disponibles <= 0:
            raise ValidationError(f"El curso «{curso}» ya no tiene cupos disponibles.", code="sin_cupos")
        if self.alumno and Inscripcion.objects.filter(alumno=self.alumno, curso=curso).exists():
            raise ValidationError("Ya estás inscrita(o) en este curso.", code="duplicado")
        return datos

    def save(self, commit=True):
        inscripcion = super().save(commit=False)
        inscripcion.alumno = self.alumno
        if commit:
            inscripcion.save()
        return inscripcion


# ---------------------------------------------------------------------------
# 3) MODELFORM – Crear curso (sólo instructores con permiso)
# ---------------------------------------------------------------------------
class CursoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            "nombre", "categoria", "nivel", "modalidad", "descripcion", "imagen_url",
            "precio", "cupos", "fecha_inicio", "fecha_fin", "horario",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "imagen_url": forms.URLInput(attrs={"placeholder": "https://images.unsplash.com/photo-..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean_nombre(self):
        nombre = sanitize_input(self.cleaned_data["nombre"])
        if len(nombre) < 5:
            raise ValidationError("El nombre del curso es demasiado corto.")
        return nombre[0].upper() + nombre[1:]

    def clean_descripcion(self):
        return sanitize_input(self.cleaned_data["descripcion"])

    def clean_fecha_inicio(self):
        inicio = self.cleaned_data["fecha_inicio"]
        if inicio < date.today():
            raise ValidationError("La fecha de inicio no puede estar en el pasado.")
        return inicio

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("fecha_inicio"), datos.get("fecha_fin")
        modalidad, cupos = datos.get("modalidad"), datos.get("cupos")
        if inicio and fin and (fin - inicio).days > 180:
            self.add_error("fecha_fin", "Un curso no puede durar más de 6 meses.")
        if modalidad == Curso.Modalidad.PRESENCIAL and cupos and cupos > 20:
            self.add_error("cupos", "El taller presencial admite como máximo 20 alumnas(os) por aforo.")
        return datos


# ---------------------------------------------------------------------------
# 4) Registro y login
# ---------------------------------------------------------------------------
class RegistroForm(BootstrapMixin, UserCreationForm):
    first_name = forms.CharField(label="Nombres", max_length=60, validators=[nombre_persona_validator])
    last_name = forms.CharField(label="Apellidos", max_length=60, validators=[nombre_persona_validator])
    email = forms.EmailField(label="Correo electrónico")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean_username(self):
        username = sanitize_input(self.cleaned_data["username"], lower=True)
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Ese nombre de usuario ya está en uso.")
        return username

    def clean_email(self):
        email = sanitize_input(self.cleaned_data["email"], lower=True)
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta con ese correo.")
        return email

    def clean_first_name(self):
        return sanitize_input(self.cleaned_data["first_name"]).title()

    def clean_last_name(self):
        return sanitize_input(self.cleaned_data["last_name"]).title()


class LoginForm(BootstrapMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

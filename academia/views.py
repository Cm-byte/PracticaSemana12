from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from .forms import ContactoForm, CursoForm, InscripcionForm, RegistroForm
from .models import Categoria, Curso, Inscripcion

MAX_CURSOS_VISTOS = 4


def _contar_visita(request):
    """Ejemplo de sesión: contador de visitas (asignación -> modified automático)."""
    request.session["visitas"] = request.session.get("visitas", 0) + 1
    if request.user.is_authenticated:
        request.session["visitas_desde_login"] = request.session.get("visitas_desde_login", 0) + 1


def inicio(request):
    _contar_visita(request)
    cursos = (
        Curso.objects.filter(activo=True)
        .select_related("categoria", "instructor")
        .annotate(n_inscritos=Count("inscripciones", filter=~Q(inscripciones__estado="cancelada")))[:6]
    )
    vistos_slugs = request.session.get("cursos_vistos", [])
    vistos = Curso.objects.filter(slug__in=vistos_slugs, activo=True)
    return render(request, "academia/inicio.html", {
        "cursos": cursos,
        "categorias": Categoria.objects.annotate(total=Count("cursos")),
        "vistos": vistos,
    })


def cursos_lista(request):
    _contar_visita(request)
    cursos = Curso.objects.filter(activo=True).select_related("categoria", "instructor")
    nivel = request.GET.get("nivel", "")
    categoria = request.GET.get("categoria", "")
    q = request.GET.get("q", "").strip()[:60]
    if nivel in Curso.Nivel.values:
        cursos = cursos.filter(nivel=nivel)
    if categoria:
        cursos = cursos.filter(categoria__slug=categoria)
    if q:
        cursos = cursos.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
    return render(request, "academia/cursos.html", {
        "cursos": cursos,
        "niveles": Curso.Nivel.choices,
        "categorias": Categoria.objects.all(),
        "filtro": {"nivel": nivel, "categoria": categoria, "q": q},
    })


def curso_detalle(request, slug):
    curso = get_object_or_404(Curso.objects.select_related("categoria", "instructor"), slug=slug, activo=True)
    # Sesión con objeto MUTABLE: modificar la lista in-place NO marca la sesión
    # como modificada, por eso se fuerza request.session.modified = True.
    vistos = request.session.setdefault("cursos_vistos", [])
    if slug in vistos:
        vistos.remove(slug)
    vistos.insert(0, slug)
    del vistos[MAX_CURSOS_VISTOS:]
    request.session.modified = True
    ya_inscrito = request.user.is_authenticated and curso.inscripciones.filter(alumno=request.user).exists()
    return render(request, "academia/curso_detalle.html", {"curso": curso, "ya_inscrito": ya_inscrito})


def contacto(request):
    """Formulario clásico (forms.Form) con patrón POST/Redirect/GET."""
    if request.method == "POST":
        form = ContactoForm(request.POST)  # nunca usar request.POST directamente
        if form.is_valid():
            form.guardar()
            messages.success(request, "¡Gracias! Te responderemos en menos de 24 horas.")
            return redirect("academia:contacto")
        messages.error(request, "Revisa los campos marcados en rojo.")
    else:
        form = ContactoForm()
    return render(request, "academia/contacto.html", {"form": form})


def registro(request):
    if request.user.is_authenticated:
        return redirect("academia:inicio")
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            alumnos, _ = Group.objects.get_or_create(name="Alumnos")
            usuario.groups.add(alumnos)
            login(request, usuario)  # rota la clave de sesión (previene session fixation)
            messages.success(request, f"¡Bienvenida(o) a TejeArte, {usuario.first_name}!")
            return redirect("academia:inscribirse")
    else:
        form = RegistroForm()
    return render(request, "registration/registro.html", {"form": form})


@login_required
def inscribirse(request):
    """ModelForm renderizado con {{ form.as_p }}."""
    inicial = {}
    if slug := request.GET.get("curso"):
        inicial["curso"] = Curso.objects.filter(slug=slug).first()
    if request.method == "POST":
        form = InscripcionForm(request.POST, alumno=request.user)
        if form.is_valid():
            inscripcion = form.save()
            messages.success(request, f"Inscripción registrada en «{inscripcion.curso}». Estado: pendiente de confirmación.")
            return redirect("academia:mis_inscripciones")
    else:
        form = InscripcionForm(initial=inicial, alumno=request.user)
    return render(request, "academia/inscripcion_form.html", {"form": form})


@login_required
def mis_inscripciones(request):
    inscripciones = request.user.inscripciones.select_related("curso", "curso__categoria")
    return render(request, "academia/mis_inscripciones.html", {"inscripciones": inscripciones})


@login_required
@require_POST
def cancelar_inscripcion(request, pk):
    # El filtro por alumno impide cancelar inscripciones ajenas (IDOR)
    inscripcion = get_object_or_404(Inscripcion, pk=pk, alumno=request.user)
    inscripcion.estado = Inscripcion.Estado.CANCELADA
    inscripcion.save(update_fields=["estado"])
    messages.info(request, f"Cancelaste tu inscripción en «{inscripcion.curso}».")
    return redirect("academia:mis_inscripciones")


class CursoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Sólo usuarios con permiso academia.add_curso (grupo Instructores)."""
    model = Curso
    form_class = CursoForm
    template_name = "academia/curso_form.html"
    permission_required = "academia.add_curso"
    raise_exception = True  # usuario logueado sin permiso -> 403 (no redirige al login)
    success_url = reverse_lazy("academia:panel_instructor")

    def form_valid(self, form):
        form.instance.instructor = self.request.user
        form.instance.activo = self.request.user.has_perm("academia.publicar_curso")
        messages.success(self.request, f"Curso «{form.instance.nombre}» creado.")
        return super().form_valid(form)


@login_required
@permission_required("academia.view_inscripcion", raise_exception=True)
def panel_instructor(request):
    cursos = (
        Curso.objects.filter(instructor=request.user)
        .annotate(n_inscritos=Count("inscripciones", filter=~Q(inscripciones__estado="cancelada")))
        .select_related("categoria")
    )
    inscripciones = Inscripcion.objects.filter(curso__instructor=request.user).select_related("alumno", "curso")[:20]
    return render(request, "academia/panel_instructor.html", {"cursos": cursos, "inscripciones": inscripciones})


@login_required
def sesion_info(request):
    """Página de auditoría: muestra lo que hay en la sesión y la configuración de cookies."""
    from django.conf import settings

    return render(request, "academia/sesion.html", {
        "datos_sesion": dict(request.session.items()),
        "session_key": (request.session.session_key or "")[:8] + "…",
        "expira": request.session.get_expiry_date(),
        "config": {
            "SESSION_ENGINE": settings.SESSION_ENGINE,
            "SESSION_COOKIE_NAME": settings.SESSION_COOKIE_NAME,
            "SESSION_COOKIE_AGE": settings.SESSION_COOKIE_AGE,
            "SESSION_COOKIE_HTTPONLY": settings.SESSION_COOKIE_HTTPONLY,
            "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
            "SESSION_EXPIRE_AT_BROWSER_CLOSE": settings.SESSION_EXPIRE_AT_BROWSER_CLOSE,
            "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
            "CSRF_COOKIE_HTTPONLY": settings.CSRF_COOKIE_HTTPONLY,
            "X_FRAME_OPTIONS": settings.X_FRAME_OPTIONS,
        },
        "permisos": sorted(p for p in request.user.get_all_permissions() if p.startswith("academia.")),
        "grupos": request.user.groups.values_list("name", flat=True),
        "request_id": getattr(request, "request_id", "-"),
    })


# --- Páginas de error --------------------------------------------------------
def error_403(request, exception=None):
    return render(request, "403.html", status=403)


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def csrf_fallido(request, reason=""):
    return render(request, "403_csrf.html", {"reason": reason}, status=403)

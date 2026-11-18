"""
Middleware personalizados de TejeArte.

Estructura de un middleware "new-style":
    __init__(get_response): se ejecuta UNA sola vez al arrancar el servidor.
    __call__(request):      se ejecuta en CADA petición.
        - código ANTES de get_response  -> fase request (antes de la vista)
        - response = self.get_response(request)  -> siguiente middleware / vista
        - código DESPUÉS               -> fase response
        - SIEMPRE debe retornar un HttpResponse.
"""
import logging
import time
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.urls import reverse

logger = logging.getLogger("tejearte.auditoria")


class AuditoriaMiddleware:
    """Registra cada petición: id, usuario, método, ruta, estado y tiempo de respuesta."""

    RUTAS_IGNORADAS = ("/static/", "/favicon.ico")

    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("AuditoriaMiddleware inicializado (una sola vez al arrancar)")

    def __call__(self, request):
        # ---- Fase REQUEST ----
        inicio = time.perf_counter()
        request.request_id = uuid.uuid4().hex[:8]

        response = self.get_response(request)

        # ---- Fase RESPONSE ----
        duracion_ms = (time.perf_counter() - inicio) * 1000
        response["X-Request-ID"] = request.request_id
        response["X-Response-Time-ms"] = f"{duracion_ms:.1f}"

        if not request.path.startswith(self.RUTAS_IGNORADAS):
            usuario = request.user.username if getattr(request, "user", None) and request.user.is_authenticated else "anonimo"
            ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "-")).split(",")[0]
            nivel = logging.WARNING if response.status_code >= 400 else logging.INFO
            logger.log(
                nivel, "[%s] %s %s %s -> %s (%.1f ms) ip=%s",
                request.request_id, usuario, request.method, request.get_full_path(),
                response.status_code, duracion_ms, ip,
            )
        return response


class CabecerasSeguridadMiddleware:
    """Agrega Content-Security-Policy y otras cabeceras de endurecimiento."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = getattr(settings, "TEJEARTE_CSP", "default-src 'self'")

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.csp)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("X-Content-Type-Options", "nosniff")
        # Evita que páginas privadas queden en caché del navegador
        if getattr(request, "user", None) and request.user.is_authenticated:
            response.setdefault("Cache-Control", "no-store, private")
        return response


class MantenimientoMiddleware:
    """
    Corta el flujo (no llama a la vista) y retorna una respuesta 503 cuando
    el modo mantenimiento está activo. El staff y el admin siguen entrando.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "TEJEARTE_MODO_MANTENIMIENTO", False):
            es_staff = request.user.is_authenticated and request.user.is_staff
            if not es_staff and not request.path.startswith(("/admin/", "/cuentas/login/", "/static/")):
                return render(request, "mantenimiento.html", status=503)
        return self.get_response(request)


class InactividadSesionMiddleware:
    """
    Cierra la sesión si el usuario no hizo peticiones durante
    TEJEARTE_INACTIVIDAD_SEGUNDOS. Guarda la marca de tiempo en la sesión.
    """

    CLAVE = "ultima_actividad"

    def __init__(self, get_response):
        self.get_response = get_response
        self.limite = getattr(settings, "TEJEARTE_INACTIVIDAD_SEGUNDOS", 900)

    def __call__(self, request):
        if request.user.is_authenticated:
            ahora = int(time.time())
            ultima = request.session.get(self.CLAVE)
            if ultima and ahora - ultima > self.limite:
                usuario = request.user.username
                logout(request)
                logger.warning("Sesión cerrada por inactividad: %s", usuario)
                messages.warning(request, "Tu sesión se cerró por inactividad. Vuelve a ingresar.")
                return redirect(f"{reverse('login')}?next={request.path}")
            # Asignar una clave marca la sesión como modificada automáticamente
            request.session[self.CLAVE] = ahora
        return self.get_response(request)

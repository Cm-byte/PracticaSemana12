"""Auditoría de autenticación mediante señales de django.contrib.auth."""
import logging

from django.contrib import messages
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

logger = logging.getLogger("tejearte.auth")


def _ip(request):
    if request is None:
        return "-"
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "-")).split(",")[0]


@receiver(user_logged_in)
def al_iniciar_sesion(sender, request, user, **kwargs):
    logger.info("LOGIN OK usuario=%s ip=%s", user.username, _ip(request))
    request.session["visitas_desde_login"] = 0


@receiver(user_logged_out)
def al_cerrar_sesion(sender, request, user, **kwargs):
    if user is not None:
        logger.info("LOGOUT usuario=%s ip=%s", user.username, _ip(request))
        messages.info(request, "Cerraste sesión correctamente. ¡Hasta la próxima clase!")


@receiver(user_login_failed)
def al_fallar_login(sender, credentials, request=None, **kwargs):
    logger.warning("LOGIN FALLIDO usuario=%s ip=%s", credentials.get("username"), _ip(request))

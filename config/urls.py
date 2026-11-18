from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from academia import views as academia_views
from academia.forms import LoginForm

admin.site.site_header = "TejeArte | Administración"
admin.site.site_title = "TejeArte Admin"
admin.site.index_title = "Gestión de la escuela de tejido"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Autenticación
    path("cuentas/login/", auth_views.LoginView.as_view(
        authentication_form=LoginForm, redirect_authenticated_user=True), name="login"),
    path("cuentas/logout/", auth_views.LogoutView.as_view(), name="logout"),  # sólo POST en Django 5
    path("cuentas/registro/", academia_views.registro, name="registro"),
    path("", include("academia.urls")),
]

handler403 = "academia.views.error_403"
handler404 = "academia.views.error_404"

from django.urls import path

from . import views

app_name = "academia"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("cursos/", views.cursos_lista, name="cursos"),
    path("cursos/nuevo/", views.CursoCreateView.as_view(), name="curso_nuevo"),
    path("cursos/<slug:slug>/", views.curso_detalle, name="curso_detalle"),
    path("contacto/", views.contacto, name="contacto"),
    path("inscribirse/", views.inscribirse, name="inscribirse"),
    path("mis-inscripciones/", views.mis_inscripciones, name="mis_inscripciones"),
    path("mis-inscripciones/<int:pk>/cancelar/", views.cancelar_inscripcion, name="cancelar_inscripcion"),
    path("panel-instructor/", views.panel_instructor, name="panel_instructor"),
    path("mi-sesion/", views.sesion_info, name="sesion"),
]

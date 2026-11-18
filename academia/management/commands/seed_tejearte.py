"""
Carga datos de demostración: grupos con permisos, usuarios, categorías y cursos.
Uso:  python manage.py seed_tejearte
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand
from django.db import transaction

from academia.models import Categoria, Curso, Inscripcion


def img(photo_id):
    return f"https://images.unsplash.com/{photo_id}?w=900&q=70&auto=format&fit=crop"


IMAGENES = {
    "palitos": img("photo-1789146501805-7221ff95bb3c"),     # manos tejiendo con café
    "lana": img("photo-1557303696-f0a415dc1b3e"),           # tejido marrón
    "carretes": img("photo-1597386983880-657bf172eedf"),    # carretes de hilo
    "crochet": img("photo-1468927201227-35e86293a0c8"),     # crochet blanco y negro
    "ovillo": img("photo-1427241107556-986c434763e3"),      # ovillo naranja
    "telar": img("photo-1727027282611-ced15b0855d0"),       # hilos de colores
}

CATEGORIAS = [
    ("Tejido a palitos", "palitos", "bi-grid-3x3", "Puntos derecho, revés, elásticos y trenzas."),
    ("Crochet", "crochet", "bi-flower1", "Cadenetas, puntos altos, amigurumis y granny squares."),
    ("Telar andino", "telar-andino", "bi-border-all", "Técnicas tradicionales del Valle del Mantaro."),
]

CURSOS = [
    ("Palitos desde cero", "palitos", "basico", "presencial", "palitos", 120, 15, "Sábados 9:00 – 12:00",
     "Aprende a montar puntos, tejer derecho y revés, y termina tu primera bufanda de alpaca."),
    ("Crochet para principiantes", "crochet", "basico", "virtual", "crochet", 90, 25, "Martes y jueves 19:00 – 20:30",
     "Cadenetas, puntos bajos y altos. Proyecto final: un posavasos y un gorro sencillo."),
    ("Amigurumis: muñecos tejidos", "crochet", "intermedio", "presencial", "ovillo", 150, 12, "Miércoles 16:00 – 18:30",
     "Anillo mágico, aumentos y disminuciones para tejer muñecos tridimensionales."),
    ("Trenzas y jacquard", "palitos", "avanzado", "presencial", "lana", 210, 10, "Viernes 17:00 – 20:00",
     "Lectura de gráficos, trenzas cruzadas y jacquard a dos colores para chompas."),
    ("Telar de cintura huanca", "telar-andino", "intermedio", "presencial", "telar", 180, 8, "Domingos 9:00 – 13:00",
     "Urdido, iconografía wanka y acabados. Clases con maestras artesanas de Hualhuas."),
    ("Teñido natural de lanas", "telar-andino", "basico", "presencial", "carretes", 100, 14, "Sábados 14:00 – 17:00",
     "Tintes con cochinilla, nogal y q'olle. Llévate tus madejas teñidas a casa."),
]


class Command(BaseCommand):
    help = "Crea datos de demostración para TejeArte"

    @transaction.atomic
    def handle(self, *args, **options):
        alumnos, _ = Group.objects.get_or_create(name="Alumnos")
        instructores, _ = Group.objects.get_or_create(name="Instructores")
        # Los alumnos NO reciben view_inscripcion global: sólo ven las suyas (vista filtrada por usuario)
        alumnos.permissions.set(Permission.objects.filter(codename__in=["view_curso", "add_inscripcion"]))
        instructores.permissions.set(Permission.objects.filter(codename__in=[
            "view_curso", "add_curso", "change_curso", "publicar_curso",
            "view_inscripcion", "change_inscripcion", "view_categoria",
        ]))

        admin, creado = User.objects.get_or_create(username="admin", defaults={
            "email": "admin@tejearte.pe", "first_name": "Administración", "is_staff": True, "is_superuser": True,
        })
        if creado:
            admin.set_password("TejeArte#2026")
            admin.save()

        rosa, creado = User.objects.get_or_create(username="rosa", defaults={
            "email": "rosa@tejearte.pe", "first_name": "Rosa", "last_name": "Huamán Ccori", "is_staff": True,
        })
        if creado:
            rosa.set_password("Instructora#2026")
            rosa.save()
        rosa.groups.add(instructores)

        lucia, creado = User.objects.get_or_create(username="lucia", defaults={
            "email": "lucia@correo.pe", "first_name": "Lucía", "last_name": "Pérez Rojas",
        })
        if creado:
            lucia.set_password("Alumna#2026")
            lucia.save()
        lucia.groups.add(alumnos)

        cats = {}
        for nombre, slug, icono, desc in CATEGORIAS:
            cats[slug], _ = Categoria.objects.update_or_create(
                slug=slug, defaults={"nombre": nombre, "icono": icono, "descripcion": desc}
            )

        hoy = date.today()
        for i, (nombre, cat, nivel, modalidad, imagen, precio, cupos, horario, desc) in enumerate(CURSOS):
            inicio = hoy + timedelta(days=7 + i * 5)
            Curso.objects.update_or_create(nombre=nombre, defaults={
                "categoria": cats[cat], "nivel": nivel, "modalidad": modalidad,
                "imagen_url": IMAGENES[imagen], "precio": Decimal(precio), "cupos": cupos,
                "horario": horario, "descripcion": desc, "instructor": rosa,
                "fecha_inicio": inicio, "fecha_fin": inicio + timedelta(weeks=6), "activo": True,
            })

        primero = Curso.objects.get(nombre="Palitos desde cero")
        Inscripcion.objects.get_or_create(alumno=lucia, curso=primero, defaults={
            "telefono": "987654321", "experiencia": "ninguna", "estado": "confirmada",
        })

        self.stdout.write(self.style.SUCCESS("Datos de TejeArte cargados."))
        self.stdout.write("  admin / TejeArte#2026     (superusuario)")
        self.stdout.write("  rosa  / Instructora#2026  (grupo Instructores)")
        self.stdout.write("  lucia / Alumna#2026       (grupo Alumnos)")

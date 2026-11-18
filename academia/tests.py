from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .forms import ContactoForm, CursoForm, InscripcionForm
from .models import Curso, Inscripcion, MensajeContacto
from .utils import sanitize_input


class BaseTejeArte(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_tejearte", stdout=open("/dev/null", "w"))
        cls.lucia = User.objects.get(username="lucia")
        cls.rosa = User.objects.get(username="rosa")
        cls.basico = Curso.objects.get(nombre="Crochet para principiantes")
        cls.avanzado = Curso.objects.get(nombre="Trenzas y jacquard")


class SanitizacionTests(TestCase):
    def test_sanitize_quita_html_y_espacios(self):
        self.assertEqual(sanitize_input("  <b>Hola</b>   mundo  "), "Hola mundo")

    def test_sanitize_lower_y_escape(self):
        self.assertEqual(sanitize_input(" ANA@Correo.PE ", lower=True), "ana@correo.pe")
        self.assertEqual(sanitize_input('5 > 3 & "x"', escapar=True), "5 &gt; 3 &amp; &quot;x&quot;")


class ContactoFormTests(BaseTejeArte):
    datos = {
        "nombre": "  maría quispe ", "email": "MARIA@Correo.pe", "telefono": "",
        "asunto": "informes", "mensaje": "Quisiera saber los horarios del curso de crochet.",
        "acepta_politica": "on",
    }

    def test_valido_normaliza_datos(self):
        form = ContactoForm(self.datos)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["nombre"], "María Quispe")
        self.assertEqual(form.cleaned_data["email"], "maria@correo.pe")

    def test_rechaza_xss(self):
        form = ContactoForm({**self.datos, "mensaje": "<script>alert('xss')</script> hola hola hola"})
        self.assertFalse(form.is_valid())
        self.assertIn("mensaje", form.errors)

    def test_rechaza_sqli(self):
        form = ContactoForm({**self.datos, "mensaje": "hola' OR '1'='1 ; DROP TABLE academia_curso"})
        self.assertFalse(form.is_valid())
        self.assertIn("mensaje", form.errors)

    def test_cross_field_telefono_obligatorio_si_inscripcion(self):
        form = ContactoForm({**self.datos, "asunto": "inscripcion"})
        self.assertFalse(form.is_valid())
        self.assertIn("telefono", form.errors)

    def test_error_global_spam(self):
        msg = "visita http://a.com http://b.com http://c.com ahora mismo"
        form = ContactoForm({**self.datos, "mensaje": msg})
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_post_guarda_y_redirige(self):
        r = self.client.post(reverse("academia:contacto"), self.datos)
        self.assertRedirects(r, reverse("academia:contacto"))
        self.assertEqual(MensajeContacto.objects.count(), 1)


class InscripcionFormTests(BaseTejeArte):
    def test_avanzado_requiere_experiencia(self):
        form = InscripcionForm({"curso": self.avanzado.pk, "telefono": "987654321", "experiencia": "ninguna"}, alumno=self.lucia)
        self.assertFalse(form.is_valid())
        self.assertIn("experiencia", form.errors)

    def test_telefono_regex(self):
        form = InscripcionForm({"curso": self.basico.pk, "telefono": "12345", "experiencia": "ninguna"}, alumno=self.lucia)
        self.assertFalse(form.is_valid())
        self.assertIn("telefono", form.errors)

    def test_duplicado_es_error_global(self):
        Inscripcion.objects.create(alumno=self.lucia, curso=self.basico, telefono="987654321")
        form = InscripcionForm({"curso": self.basico.pk, "telefono": "987654321", "experiencia": "ninguna"}, alumno=self.lucia)
        self.assertFalse(form.is_valid())
        self.assertIn("Ya estás inscrita", str(form.non_field_errors()))


class CursoFormTests(BaseTejeArte):
    def test_validacion_modelo_fechas(self):
        hoy = date.today() + timedelta(days=3)
        form = CursoForm({
            "nombre": "Curso de prueba", "categoria": self.basico.categoria.pk, "nivel": "basico",
            "modalidad": "virtual", "descripcion": "Descripción", "precio": "50", "cupos": 10,
            "imagen_url": "https://images.unsplash.com/photo-1", "horario": "Lunes",
            "fecha_inicio": hoy, "fecha_fin": hoy - timedelta(days=1),
        })
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_fin", form.errors)

    def test_imagen_solo_por_enlace_unsplash(self):
        form = CursoForm({"imagen_url": "https://otro-sitio.com/x.jpg"})
        form.is_valid()
        self.assertIn("imagen_url", form.errors)


class AutenticacionTests(BaseTejeArte):
    def test_login_required_redirige(self):
        r = self.client.get(reverse("academia:mis_inscripciones"))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('academia:mis_inscripciones')}")

    def test_registro_agrega_a_grupo_alumnos(self):
        r = self.client.post(reverse("registro"), {
            "username": "Carla", "first_name": "carla", "last_name": "rojas", "email": "carla@correo.pe",
            "password1": "TejerEsLoMax#1", "password2": "TejerEsLoMax#1",
        })
        self.assertRedirects(r, reverse("academia:inscribirse"))
        u = User.objects.get(username="carla")
        self.assertTrue(u.groups.filter(name="Alumnos").exists())
        self.assertEqual(u.first_name, "Carla")

    def test_alumna_no_puede_crear_curso_403(self):
        self.client.force_login(self.lucia)
        self.assertEqual(self.client.get(reverse("academia:curso_nuevo")).status_code, 403)
        self.assertEqual(self.client.get(reverse("academia:panel_instructor")).status_code, 403)

    def test_instructora_si_puede(self):
        self.client.force_login(self.rosa)
        self.assertEqual(self.client.get(reverse("academia:curso_nuevo")).status_code, 200)
        self.assertEqual(self.client.get(reverse("academia:panel_instructor")).status_code, 200)

    def test_no_puede_cancelar_inscripcion_ajena(self):
        ajena = Inscripcion.objects.get(alumno=self.lucia)
        otra = User.objects.create_user("eva", password="x-Prueba#123")
        self.client.force_login(otra)
        r = self.client.post(reverse("academia:cancelar_inscripcion", args=[ajena.pk]))
        self.assertEqual(r.status_code, 404)

    def test_logout_solo_post(self):
        self.client.force_login(self.lucia)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class CsrfTests(BaseTejeArte):
    def test_post_sin_token_csrf_403(self):
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("academia:contacto"), ContactoFormTests.datos)
        self.assertEqual(r.status_code, 403)


class MiddlewareSesionTests(BaseTejeArte):
    def test_cabeceras_seguridad(self):
        r = self.client.get(reverse("academia:inicio"))
        self.assertIn("default-src 'self'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertIn("X-Request-ID", r)
        self.assertIn("X-Response-Time-ms", r)

    def test_sesion_contador_y_lista_mutable(self):
        self.client.get(reverse("academia:inicio"))
        self.client.get(reverse("academia:inicio"))
        self.assertEqual(self.client.session["visitas"], 2)
        self.client.get(self.basico.get_absolute_url())
        self.assertEqual(self.client.session["cursos_vistos"], [self.basico.slug])

    @override_settings(TEJEARTE_INACTIVIDAD_SEGUNDOS=-1)
    def test_inactividad_cierra_sesion(self):
        self.client.force_login(self.lucia)
        s = self.client.session
        s["ultima_actividad"] = 1
        s.save()
        r = self.client.get(reverse("academia:mis_inscripciones"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    @override_settings(TEJEARTE_MODO_MANTENIMIENTO=True)
    def test_mantenimiento_corta_flujo(self):
        self.assertEqual(self.client.get(reverse("academia:inicio")).status_code, 503)


class AdminTests(BaseTejeArte):
    def test_admin_listados_y_accion(self):
        admin = User.objects.get(username="admin")
        self.client.force_login(admin)
        for url in ["admin:academia_curso_changelist", "admin:academia_inscripcion_changelist", "admin:academia_mensajecontacto_changelist"]:
            self.assertEqual(self.client.get(reverse(url)).status_code, 200)
        r = self.client.post(reverse("admin:academia_curso_changelist"), {
            "action": "despublicar", "_selected_action": [self.basico.pk],
        })
        self.assertEqual(r.status_code, 302)
        self.basico.refresh_from_db()
        self.assertFalse(self.basico.activo)

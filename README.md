# TejeArte – Escuela de Tejido

**Guía Práctica Semana 12 · Desarrollo de Aplicaciones Web (IS093A)**
Unidad II: Desarrollo Web Fullstack — Formularios, Django Admin, Middleware, Sesiones, Autenticación y Autorización.
Alumna: **Ramos Tacza Camilda**

Sistema web para una escuela de tejido (palitos, crochet y telar andino) en Huancayo: catálogo de cursos, inscripciones de alumnas(os), formulario de contacto, panel de instructoras y administración operativa. Íconos con **Bootstrap Icons** (sin emojis) e imágenes **por enlace** (Unsplash, campo `imagen_url`).

---

## 1. Instalación

```bash
python -m venv venv
# Windows: venv\Scripts\activate     Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_tejearte      # grupos, permisos, usuarios y cursos de demo
python manage.py runserver
```

Abrir http://127.0.0.1:8000/ y http://127.0.0.1:8000/admin/

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `TejeArte#2026` | Superusuario |
| `rosa` | `Instructora#2026` | Grupo **Instructores** (is_staff, crea cursos) |
| `lucia` | `Alumna#2026` | Grupo **Alumnos** |

Pruebas automatizadas (25 tests): `python manage.py test academia -v 2`

---

## 2. Estructura

```
tejearte/
├── config/settings.py        # sesiones, CSRF, cabeceras, MIDDLEWARE, LOGGING
├── academia/
│   ├── models.py             # Categoria, Curso, Inscripcion, MensajeContacto (+ Model.clean)
│   ├── forms.py              # ContactoForm (clásico), InscripcionForm, CursoForm, RegistroForm
│   ├── validators.py         # regex celular/nombre, sin HTML, sin SQL, sólo enlaces Unsplash
│   ├── utils.py              # sanitize_input(): strip, strip_tags, lower, escape
│   ├── admin.py              # ModelAdmin personalizados, @admin.display, acciones masivas
│   ├── middleware.py         # Auditoria, CabecerasSeguridad, Mantenimiento, InactividadSesion
│   ├── signals.py            # log de LOGIN OK / LOGIN FALLIDO / LOGOUT
│   ├── views.py              # @login_required, @permission_required, PermissionRequiredMixin
│   └── tests.py
├── templates/                # base.html + academia/ + registration/ + 403/404
├── static/css/tejearte.css
├── logs/auditoria.log        # se genera al ejecutar
└── pruebas_auth.http         # peticiones para REST Client / Postman
```

---

## 3. Desarrollo por fases

### Fase 1 – Formularios y plantillas
* **Formulario clásico** `ContactoForm(forms.Form)` → `/contacto/`, renderizado campo por campo con errores por campo y `form.non_field_errors`; guarda con patrón POST/Redirect/GET.
* **ModelForm** `InscripcionForm` → `/inscribirse/`, renderizado con `{{ form.as_p }}` y `{{ form.errors }}`.
* Todos los `<form method="post">` incluyen `{% csrf_token %}`.
* Nunca se guarda desde `request.POST`: siempre `Form(request.POST)` → `is_valid()` → `save()`.

### Fase 2 – Validación y sanitización (3 niveles)
| Nivel | Dónde | Ejemplo |
|---|---|---|
| Campo | validadores + `clean_<campo>()` | celular `^9\d{8}$`, nombre sólo letras, correo temporal rechazado, `validar_sin_html`, `validar_sin_sql` |
| Formulario | `clean()` cross-field | asunto "inscripción" exige celular (`add_error`), curso avanzado exige experiencia, sin cupos/duplicado (error `__all__`) |
| Modelo | `Curso.clean()` | `fecha_fin` no puede ser anterior a `fecha_inicio` |

`sanitize_input()` aplica `strip()`, normalización Unicode, elimina caracteres de control, `strip_tags()`, `lower()` y `escape()` opcionales. Las plantillas escapan la salida (autoescape) y el ORM parametriza consultas.

### Fase 3 – Django Admin
* `CursoAdmin`: `list_display`, `list_filter`, `search_fields`, `readonly_fields`, `fieldsets`, `date_hierarchy`, `prepopulated_fields`, `autocomplete_fields`, inline de inscripciones, `list_select_related` + `annotate` (sin N+1).
* Campos calculados con `@admin.display`: precio en soles, cupos libres con color, vista previa de la imagen enlazada.
* Acciones masivas `(self, request, queryset)`: publicar / despublicar (sólo con permiso `publicar_curso`), exportar CSV, confirmar / cancelar inscripciones, marcar mensajes atendidos.
* El modelo `User` usa el `UserAdmin` de Django: la contraseña sólo se muestra como hash con enlace de cambio.

### Fase 4 – Middleware y sesiones
| Middleware | Qué hace |
|---|---|
| `CabecerasSeguridadMiddleware` | `Content-Security-Policy`, `Permissions-Policy`, `Cache-Control: no-store` en páginas privadas |
| `AuditoriaMiddleware` | `X-Request-ID`, `X-Response-Time-ms` y log de usuario/método/ruta/estado/tiempo |
| `MantenimientoMiddleware` | corta el flujo y retorna 503 sin llamar a la vista (`TEJEARTE_MODO_MANTENIMIENTO=True`) |
| `InactividadSesionMiddleware` | cierra la sesión tras 15 min sin actividad |

Orden: en el request se ejecutan de arriba hacia abajo y en el response en orden inverso. Sesiones: `SESSION_ENGINE=db`, cookie `tejearte_sid` HttpOnly + SameSite=Lax, 30 min, `SESSION_EXPIRE_AT_BROWSER_CLOSE`. En `curso_detalle` se modifica una lista dentro de la sesión, por eso se usa `request.session.modified = True`. `/mi-sesion/` muestra el contenido de la sesión y la configuración.

Autorización: `@login_required` (mis inscripciones), `@permission_required` (panel instructora), `LoginRequiredMixin + PermissionRequiredMixin` (crear curso → 403 para alumnas), cancelar sólo inscripciones propias (evita IDOR), logout sólo por POST.

### Fase 5 – Integración y auditoría
Flujo: registro → login → acceso restringido → admin → logout. Revisar en DevTools las cookies y las cabeceras `X-Frame-Options: DENY` y `Content-Security-Policy`; revisar `logs/auditoria.log`.

```bash
python manage.py check --deploy                      # en desarrollo muestra advertencias (DEBUG=True)
# Producción (PowerShell: $env:DJANGO_DEBUG="False" ...)
DJANGO_DEBUG=False DJANGO_SECRET_KEY="<clave nueva>" DJANGO_ALLOWED_HOSTS=tejearte.pe python manage.py check --deploy
# -> System check identified no issues (0 silenced).
```
Generar/rotar la SECRET_KEY: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`

---

## 4. Subir a GitHub

```bash
git init
git add .
git commit -m "Semana 12: formularios, admin, middleware, sesiones y auth - TejeArte"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/tejearte-semana12.git
git push -u origin main
```
`db.sqlite3`, `.env` y los logs están en `.gitignore`.

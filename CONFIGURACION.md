# Configuración de ASEG AuditorIA

## Secretos requeridos

Configure los siguientes valores en los secretos de Streamlit Cloud. No agregue
credenciales reales al repositorio.

- `GEMINI_API_KEY`: clave de acceso a Gemini.
- `GEMINI_MODEL`: modelo explícito; inicialmente `gemini-2.5-flash`.
- `DATABASE_URL`: conexión agrupada del proyecto Neon `aseg-auditor-ia`.
- `DATABASE_URL_ADMIN`: conexión directa opcional para migraciones e importaciones.
- `APP_USER_ID`: identificador estable del usuario mientras se incorpora autenticación.

La aplicación continúa funcionando con una caché local cuando `DATABASE_URL` no
está disponible, pero ese modo es temporal y no garantiza permanencia.

## Persistencia

El esquema se documenta en `sql/001_persistencia_expedientes.sql`. Los resultados
se identifican por expediente, categoría, huella SHA-256, modelo y versión del
prompt. Cambiar el modelo o el prompt provoca un nuevo análisis sin sobrescribir
silenciosamente el resultado anterior.

## Catálogo maestro

El esquema del catálogo se agrega con `sql/002_catalogo_maestro.sql`. La carga del
Excel es transaccional: primero se valida el archivo completo y después se guarda
como una importación versionada. Una importación sólo se convierte en la fuente
vigente cuando se ejecuta con `--activar`.

Validación local, sin modificar Neon:

```bash
python -m scripts.importar_catalogo Catalogo_Maestro_ASEG.xlsx --solo-validar
```

Importación y activación controlada:

```bash
DATABASE_URL_ADMIN="..." python -m scripts.importar_catalogo \
  Catalogo_Maestro_ASEG.xlsx --activar
```

La aplicación consulta exclusivamente los documentos que estén activos,
aprobados y dentro de su vigencia. Los registros `Pendiente` o `Revisado` se
conservan en Neon, pero no se convierten en reglas operativas.

### Motor genérico de análisis

Para cada documento aprobado, la aplicación carga desde Neon los criterios de
identificación, datos clave, fundamento normativo, campos de extracción y
procedimientos de validación. Con esa definición construye un análisis
estructurado que incluye valor, evidencia, página y confianza.

Cuando un tipo documental todavía no tiene filas en `CAMPOS_EXTRACCION`, los
campos operativos se derivan de la lista `datos_clave_a_validar` del documento.
Los nombres, el orden y los procedimientos devueltos por la IA se vuelven a
normalizar contra el catálogo antes de guardarse.

Los campos o procedimientos cuyo `estado_revision` no sea `Aprobado` pueden
participar en una revisión preliminar, pero la interfaz los identifica
expresamente como configuración pendiente de aprobación. La IA utiliza
`NO_DETERMINABLE` cuando el PDF no contiene evidencia suficiente y sus resultados
no sustituyen el juicio profesional del auditor.

La clave de procesamiento incluye una firma de la configuración del documento.
Cuando cambian sus criterios, campos o procedimientos, el archivo puede volver a
analizarse aunque el PDF y el modelo sean los mismos.

Use preferentemente la conexión directa para ejecutar migraciones o importar el
catálogo. Mantenga la conexión agrupada en `DATABASE_URL` para el uso normal de
Streamlit.

## Migración desde la versión anterior

La caché `cache_app.json` no se importa automáticamente porque no contiene una
identificación confiable del usuario ni del expediente. Puede conservarse como
respaldo antes del despliegue y migrarse posteriormente mediante una herramienta
controlada.

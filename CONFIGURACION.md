# Configuración de ASEG AuditorIA

## Secretos requeridos

Configure los siguientes valores en los secretos de Streamlit Cloud. No agregue
credenciales reales al repositorio.

- `GEMINI_API_KEY`: clave de acceso a Gemini.
- `GEMINI_MODEL`: modelo explícito; inicialmente `gemini-2.5-flash`.
- `DATABASE_URL`: conexión agrupada del proyecto Neon `aseg-auditor-ia`.
- `APP_USER_ID`: identificador estable del usuario mientras se incorpora autenticación.

La aplicación continúa funcionando con una caché local cuando `DATABASE_URL` no
está disponible, pero ese modo es temporal y no garantiza permanencia.

## Persistencia

El esquema se documenta en `sql/001_persistencia_expedientes.sql`. Los resultados
se identifican por expediente, categoría, huella SHA-256, modelo y versión del
prompt. Cambiar el modelo o el prompt provoca un nuevo análisis sin sobrescribir
silenciosamente el resultado anterior.

## Migración desde la versión anterior

La caché `cache_app.json` no se importa automáticamente porque no contiene una
identificación confiable del usuario ni del expediente. Puede conservarse como
respaldo antes del despliegue y migrarse posteriormente mediante una herramienta
controlada.


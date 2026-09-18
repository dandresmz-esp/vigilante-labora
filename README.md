# Vigilante LABORA, Alzira y Silla

Primera versión sin IA: descarga páginas y calendarios, descubre enlaces, compara texto y prepara avisos. No usa APIs de modelos ni tokens. No presenta solicitudes.

**No está desplegado ni aceptado en producción.** Se han incorporado los tablones electrónicos y comprobado su paginación: Alzira, 14 anuncios en dos páginas; Silla, 77 anuncios en tres páginas (17/09/2026). Esto verifica la lectura de esos listados, no acredita cobertura universal de cada ayuntamiento. El correo y la supervisión externa se deben configurar y verificar antes de activar la programación.

## Uso local y auditoría

Python 3.12 o posterior:

```text
python -m pip install -r requirements.txt
python fetch_fixtures.py
python -m unittest discover -s tests -v
python monitor.py
```

El último comando solo lee fuentes y prepara `runtime/aviso_preparado.txt`; no envía nada. `runtime/informe.json` muestra estado por entidad, fallos y cobertura. Código de salida 2 significa comprobación incompleta o fallo de entrega. Los huecos municipales son visibles aunque todas las descargas respondan.

Los PDF escaneados requieren Tesseract con idiomas español y catalán. GitHub instala ese lector. Si no existe en el ordenador, se registra un fallo de lectura; no se interpreta como ausencia de novedades. El OCR y sus fechas deben comprobarse sobre muestras antes de aceptación.

El primer pase prepara también avisos de documentos históricos para establecer la referencia; **no significa que las plazas estén abiertas**. Las fechas se extraen del documento; un plazo relativo no se convierte automáticamente en fecha de cierre. Los documentos con varias fechas requieren revisión. No se deduce el año del reloj ni se filtra por titulación.

## Activación en GitHub

1. Crear un repositorio para este proyecto. Subir únicamente el código, configuración, pruebas y documentación. No subir `runtime`, documentación personal, certificados, secretos ni el ZIP de la candidatura.
2. Ejecutar manualmente «Pruebas de aceptación reproducibles».
3. Ejecutar «Vigilante LABORA Alzira Silla» con `enviar=false`. Revisar cobertura y recursos alcanzados.
4. Configurar secretos de Actions: `SMTP_HOST`, `SMTP_PORT` (465), `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_FROM`, `ALERT_TO` y `HEARTBEAT_URL`. Destinatario: configurar el correo elegido; introducirlo como secreto, no publicarlo en el código.
5. Usar una credencial SMTP específica del servicio. No escribir la contraseña principal de correo en archivos ni en el chat.
6. Configurar un servicio externo, por ejemplo [Healthchecks](https://healthchecks.io/docs/configuring_checks/), con avisos al correo elegido. `HEARTBEAT_URL` es la dirección HTTPS de recepción. En producción: periodo de 1 hora y margen de 1 hora. GitHub envía la señal cada hora, también fuera de la franja de lectura de fuentes, después de conservar el estado. Así se detecta el silencio en unas dos horas sin depender del ordenador. Para la prueba de ausencia de ejecución: con la programación todavía desactivada, usar temporalmente periodo de 1 minuto y margen de 1 minuto; ejecutar una señal manual con «Comprobar canales de aviso»; no enviar ninguna más y confirmar que el servicio externo avisa. Después cambiar a 1 hora + 1 hora antes de activar. No declarar esta prueba superada por enviar una señal manual de error.
7. Autorizar y ejecutar una entrega manual. Confirmar recepción real en el correo y notificación del móvil. La aceptación por el servidor SMTP no acredita recepción ni lectura.
8. Solo tras la auditoría, crear variable `VIGILANTE_ACTIVO=true`. Por defecto las ejecuciones programadas están desactivadas.

La programación se dispara en el minuto 17 y el programa aplica horario Europe/Madrid (incluidos cambios de hora). Lee cada hora de 8 a 20 laborables, además de las 6 y 22; fines de semana a las 9. Los festivos se comprueban igual que otros días de la semana, sin reducir cobertura.

El estado y la cola de avisos se conservan con historial en la rama `estado-vigilante`; no se usa una caché temporal como base de datos. La rama conserva versiones del estado y del informe, no los PDF. Los artefactos de Actions caducan. Las actualizaciones de estado generan actividad en el repositorio; aun así el control externo debe detectar ejecuciones que no arrancan o programaciones desactivadas.

Los avisos se retienen si falla SMTP y se reintentan. Se envía un resumen por pase; los cambios pendientes de una misma fuente se sustituyen por su estado más reciente. Si el servidor acepta un correo pero el proceso muere antes de guardar estado, podría repetirse; se prioriza no perderlo. El programa no expone secretos en los informes. Conserva avances parciales durante la lectura, por si la ejecución se interrumpe.

El inventario inicial registra los enlaces históricos sin descargar de golpe centenares de PDF antiguos. Las páginas se comparan incluyendo esos enlaces; cuando aparece uno nuevo, el siguiente pase lee el documento y extrae sus fechas. Los PDF ya verificados conservan una referencia del archivo y, cuando el servidor lo permite, se consultan con ETag/Last-Modified. Si no han cambiado se reutiliza la lectura anterior; si cambian los bytes, se vuelve a comparar el texto normalizado. Las copias históricas de prueba están incluidas con sus hashes y sus URLs oficiales, para que una caída actual de una web no impida reproducir un caso pasado. La disponibilidad actual se verifica por separado con «Comprobar fuentes principales desde GitHub» y el barrido completo.

Si una web acumula tres descargas fallidas por conexión o errores de servidor, se suspenden las siguientes descargas de esa web durante ese pase. Se registran como pendientes/fallidas, nunca como ausencia de novedades. La siguiente ejecución vuelve a intentarlo. Las peticiones que ya estaban en curso pueden terminar después de alcanzar el límite.

## Cobertura y límites

- LABORA: cinco páginas de programas; descubrimiento de calendarios de cualquier año enlazado.
- Alzira: índice de formación IDEA, Escola Taller y páginas de programas descubiertas.
- Silla: índice de programas mixtos y sus páginas/documentos.
- Sagunt: sección municipal de empleo, Escuela Taller y ofertas de Sagunto Emplea.
- Picanya: ofertas de su portal municipal y noticias oficiales filtradas por empleo, formación y talleres. Incluye el promotor FOTAE/2026/33/46, Escola de Jardineria José Casabán II.
- Tablones municipales de Alzira y Silla: lectores de listado y paginación incorporados. Compara todos los títulos y fechas del listado; profundiza en anuncios con términos de empleo, formación o talleres. Una modificación de una ficha cuyo título/listado no cambia podría pasar inadvertida si no fue seleccionada para lectura; revisar esta limitación en la auditoría.
- BOP y otros municipios: fuera de esta primera versión.
- Morella: solo material histórico de prueba; no se amplía la vigilancia a esa entidad.
- Límite de 2000 recursos por pase y profundidad de dos niveles para páginas; los PDF enlazados se leen. Alcanzar el límite genera incidencia visible. La lista debe revisarse si aumenta.
- El contenido nuevo o modificado se avisa sin decidir automáticamente si pertenece a una plaza apta para la persona interesada. Puede incluir resultados, alumnado o documentos históricos; no son ofertas garantizadas.
- La extracción de fechas es conservadora y no interpreta jurídicamente plazos, festivos ni discrepancias. La alerta siempre conserva el enlace oficial.
- No hay garantía de ejecución puntual de GitHub ni disponibilidad de las páginas.

## Entrega a Claude

Claude puede ejecutar las pruebas, contrastar los PDF con sus fuentes, modificar datos de prueba y revisar `AUDITORIA.md`. No se considera independiente que el constructor ejecute sus propias pruebas. La aceptación final exige las pruebas externas de correo/móvil y de ausencia de ejecución, además de resolver o aceptar expresamente los huecos de cobertura.


# Protocolo de aceptación independiente

Estado inicial: NO ACEPTADO / NO DESPLEGADO. Este documento no certifica funcionamiento en producción.

| Prueba | Evidencia exigida |
|---|---|
| Alzira IMAI0110 | Detectar el puesto y el intervalo 15–17/09/2026 en el calendario real; comprobar que corresponde a Alzira, no a otra fila. |
| Silla abril | Detectar jardinería y plazo 17–21/04/2026 en el edicto real. |
| Silla mayo | Detectar nueva convocatoria y plazo 14–18/05/2026; no confundirla con abril. |
| Morella febrero y marzo | Extraer la regla literal de plazo; comprobar las inconsistencias del original. No inventar la fecha final. |
| Cambio de plazo | Modificar únicamente el cierre; tiene que generar cambio. |
| PDF regenerado | Modificar CSV/fecha de firma, conservar publicación/plazo; no debe generar novedad. |
| Enlace nuevo | Añadir calendario 2026 a página que solo tenía 2025; tiene que descubrirse. |
| PDF escaneado | Leer una muestra con OCR y contrastar puesto y fechas a mano. |
| Descarga caída | Conservar último éxito, marcar fuente fallida y preparar aviso. |
| Página vacía/estructura nueva | No declarar lectura correcta por HTTP 200. |
| Persistencia | Dos ejecuciones consecutivas: la segunda no repite novedades idénticas. Reinicio conserva cola. |
| SMTP fallido | Los avisos permanecen pendientes; reintentar cuando vuelva. |
| Recepción real | El destinatario confirma correo y notificación en móvil, incluyendo enlace y plazo. |
| No ejecución | Pausar GitHub deliberadamente y recibir aviso del servicio EXTERNO dentro de la tolerancia configurada. |
| Hueco de cobertura | Alzira/Silla no pueden figurar como completas si el tablón sigue sin validar. |

Registrar fecha, versión del código, prueba, resultado, enlaces/archivos de evidencia, auditor y limitaciones. No marcar las pruebas de integración como superadas con simulaciones locales.

Para reproducir: instalar `requirements.txt`, ejecutar `fetch_fixtures.py` y `python -m unittest discover -s tests -v`. Las descargas de prueba tienen manifiesto SHA-256 local; las fuentes oficiales pueden cambiar y eso debe investigarse, no actualizar automáticamente los resultados esperados.


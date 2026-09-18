# Prueba de acceso alternativa a LABORA

Estado: preparado y probado localmente; NO desplegado ni validado contra LABORA desde Cloudflare.

Los servidores probados de GitHub (Ubuntu, Windows y macOS) no conectaron con LABORA. Esta pieza permite probar el acceso desde otra red, cerca de Madrid, manteniendo el programa principal. Solo admite páginas y documentos públicos de LABORA, requiere una clave y conserva los bytes originales. No usa IA.

Se necesita una cuenta Cloudflare en el plan gratuito. No activar un plan de pago. Antes de incorporarlo al vigilante, hay que verificar desde GitHub las cinco páginas de programas y sus calendarios reales. Si esa prueba falla, no darlo por solución operativa.

La clave `RELAY_TOKEN` debe introducirse como secreto del servicio y de GitHub, nunca en el código. Configuración de región: [documentación oficial](https://developers.cloudflare.com/workers/configuration/placement/). Límites: [plan gratuito de Workers](https://developers.cloudflare.com/workers/platform/limits/).

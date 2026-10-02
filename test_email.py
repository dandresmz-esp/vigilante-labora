"""Send a clearly identified delivery test using the configured mail channel."""

from catalog import REGISTER_URL
from monitor import send_mail


send_mail(
    "PRUEBA — así verás un aviso de ACCIÓN HOY",
    """PRUEBA DE CORREO DEL VIGILANTE

Este mensaje comprueba que los avisos llegan a tu buzón. No hay ninguna plaza ni plazo anunciados en este correo.

EJEMPLO DEL AVISO QUE RECIBIRÁS

ACCIÓN HOY — [Entidad promotora]
Plaza: [Puesto publicado en el anuncio]
Plazo: [Fecha de apertura] a [Fecha límite]
Enlace oficial: [Enlace al anuncio de selección]

QUÉ HACER AL RECIBIR UN AVISO REAL
1. Abre el anuncio oficial ese mismo día.
2. Comprueba la plaza, los requisitos y la fecha límite.
3. Si cumples los requisitos, prepara y presenta la solicitud.
4. Guarda el justificante de presentación.

Puedes traer el correo a este chat y pedir: «Comprueba si puedo presentarme y qué papeles necesito».

Si el asunto dice REVISAR HOY, comprueba el anuncio ese día porque el plazo aún necesita confirmación. Si dice FALLO DEL VIGILANTE, avisa de una fuente que no se ha podido comprobar.

Página de plazas y plazos: """ + REGISTER_URL + "\n",
)
print("Correo de prueba enviado")

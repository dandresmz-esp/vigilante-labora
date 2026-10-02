"""Send a clearly identified delivery test using the configured mail channel."""

from catalog import REGISTER_URL
from monitor import send_mail


send_mail(
    "PRUEBA — aviso del vigilante de talleres",
    """PRUEBA DE CORREO DEL VIGILANTE

Este mensaje comprueba que los avisos llegan a tu buzón. No hay ninguna plaza ni plazo anunciados en este correo.

Cuando se detecte una selección de personal, el aviso indicará la entidad, el plazo encontrado y el enlace al anuncio oficial para presentar la solicitud.

Página de plazas y plazos: """ + REGISTER_URL + "\n",
)
print("Correo de prueba enviado")

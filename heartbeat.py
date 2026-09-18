"""Signal life only after the workflow has persisted its state and delivered alerts."""
import argparse,json,os,sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen

def send():
 url=os.environ.get('HEARTBEAT_URL','')
 if not url or urlsplit(url).scheme!='https':raise ValueError('Falta configurar HEARTBEAT_URL con HTTPS')
 with urlopen(Request(url,data=b'completed',method='POST'),timeout=20) as response:response.read(100)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check-outcome',required=True);a=p.parse_args()
 try:
  report=Path('runtime/informe.json')
  data=json.loads(report.read_text(encoding='utf8')) if report.exists() else None
  if data:
   if data.get('delivery') not in ('sin_novedades','aceptada_por_SMTP_pendiente_confirmar_recepcion'):
    raise RuntimeError('No se confirmó la entrega de avisos; no emitir señal de vida')
  elif a.check_outcome!='success':raise RuntimeError('Comprobación interrumpida; no emitir señal de vida')
  # No report + successful check = scheduled skip outside source-reading hours.
  send()
  if data:
   data['external_watchdog']='senal_enviada';report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
  print('Señal de vida confirmada después de conservar el estado')
 except Exception as exc:
  print('No se confirmó la señal de vida: '+type(exc).__name__);sys.exit(2)

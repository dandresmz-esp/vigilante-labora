"""Public historical cases for independent audit; no user application documents."""
import hashlib,json,sys,time
from pathlib import Path
from urllib.request import urlopen,Request
from concurrent.futures import ThreadPoolExecutor
SOURCES={
 'alzira_calendario.pdf':'https://labora.gva.es/documents/d/labora/fechas-presen-documen-festa-2025-33-pdf',
 'alzira_puesto.pdf':'https://www.idea-alzira.com/_files/ugd/bfeeef_97f7d3f625f64c0eab14a5b633016238.pdf',
 'silla_abril.pdf':'https://silla.e-oer.com/wp-content/uploads/sites/20/2026/04/62-Edicte-publicacio-seleccio-vacant-docent-jardinera-SEFYCU-8016520.pdf',
 'silla_mayo.pdf':'https://silla.e-oer.com/wp-content/uploads/sites/20/2026/05/73_Edicte-publicacio-convocatoria-seleccio_Vacnt-docent-jardineria-SEFYCU-8150042.pdf',
 'morella_febrero.pdf':'https://www.morella.net/wp-content/uploads/2026/02/3.-Oferta-docente-Taller-Empleo-Morella-2025-EOCB-FICHAS-Y-BASES.pdf',
 'morella_marzo.pdf':'https://www.morella.net/wp-content/uploads/2026/03/Oferta-docente-TE-Morella-especialidad-EOCB-Bases-Fichas.pdf'}
ROOT=Path(__file__).resolve().parent/'tests'/'fixtures'
def download(item):
 name,url=item
 cached=ROOT/name
 if cached.exists():
  data=cached.read_bytes()
  manifest_path=ROOT/'manifest.json'
  expected=json.loads(manifest_path.read_text(encoding='utf8')).get(name,{}).get('sha256') if manifest_path.exists() else None
  if not expected or hashlib.sha256(data).hexdigest()!=expected:raise ValueError(name+': copia histórica sin hash verificado')
 else:
  with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/pdf'}),timeout=45) as response:data=response.read(24000000)
 if not data.startswith(b'%PDF'):raise ValueError(name+': no es PDF')
 (ROOT/name).write_bytes(data)
 return name,{'url':url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
if __name__=='__main__':
 ROOT.mkdir(parents=True,exist_ok=True)
 manifest={};failed={}
 with ThreadPoolExecutor(3) as pool:
  futures={name:pool.submit(download,(name,url)) for name,url in SOURCES.items()}
  for name,future in futures.items():
   try:
    key,value=future.result();manifest[key]=value
   except Exception as exc:failed[name]=str(exc)
 (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 (ROOT/'download_errors.json').write_text(json.dumps(failed,indent=2),encoding='utf-8')
 print('Descargados',len(manifest),'casos históricos')
 if failed:
  print('Aceptación pendiente; no descargados:',', '.join(failed))
  sys.exit(2)

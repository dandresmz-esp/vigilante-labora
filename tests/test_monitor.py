import io,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from pypdf import PdfWriter
import monitor as m

class Logic(unittest.TestCase):
 def test_signature_only_no_alert(self):
  a='Convocatoria\nCSV: A1\nFirmado electrónicamente el 10/09/2026 09:32\nPlazo del 15/09/2026 al 17/09/2026'
  b=a.replace('A1','B2').replace('10/09/2026 09:32','11/09/2026 11:50')
  self.assertEqual(m.normalize(a),m.normalize(b))
 def test_deadline_change_preserved(self):
  a='Plazo del 15/09/2026 al 17/09/2026'
  self.assertNotEqual(m.normalize(a),m.normalize(a.replace('17/','18/')))
 def test_publication_not_removed(self):
  a='FIRMAT PER\nAlcalde\n16/4/2026\nSEGELL\nPublicat a tauler d’anuncis electrònic\n16/4/2026'
  self.assertEqual(m.normalize(a),m.normalize(a.replace('Alcalde\n16/4','Alcalde\n17/4')))
  self.assertNotEqual(m.normalize(a),m.normalize(a.replace('electrònic\n16/4','electrònic\n17/4')))
 def test_numeric_dates(self):
  self.assertEqual(m.details('DEL 15/09/2026 AL 17/09/2026')['deadlines'][0]['end'],'2026-09-17')
 def test_valencian_dates(self):
  self.assertEqual(m.details('del 17 al 21 de d’abril de 2026')['deadlines'][0]['end'],'2026-04-21')
 def test_relative_not_invented(self):
  d=m.details('1 día hábil desde la publicación en el tablón')
  self.assertTrue(d['review_required']);self.assertEqual(d['deadlines'],[])
 def test_discover_new_link(self):
  p=m.Page();p.feed('<p>Talleres 2026</p><a href="/documents/d/labora/calendario-2026">calendario de presentación</a>')
  c=m.candidates(p,'https://labora.gva.es/es/test','LABORA',0)
  self.assertEqual(len(c),1);self.assertEqual(c[0]['kind'],'pdf')
 def test_ignore_scripts(self):
  p=m.Page();p.feed('<script>999random</script><p>Convocatoria</p>');self.assertEqual(p.text(),'Convocatoria')
 def test_http_304_reuses_verified_text(self):
  r={'entity':'Silla','url':'https://silla.e-oer.com/test.pdf','kind':'pdf','_cache':{'byte_hash':'raw','extraction_version':m.EXTRACTION_VERSION,'hash':'normalized','details':{},'http_cache':{'etag':'v1'}}}
  with patch.object(m,'fetch',return_value=(None,'application/pdf',{'etag':'v1'})),patch.object(m,'extract_pdf') as extract:
   result=m.inspect_resource(r)
  self.assertTrue(result['ok']);self.assertEqual(result['hash'],'normalized');extract.assert_not_called()
 def test_new_links_before_detached_history(self):
  root={'entity':'Silla','url':'https://silla.e-oer.com/root','kind':'page'}
  fresh={'entity':'Silla','url':'https://silla.e-oer.com/new.pdf','kind':'pdf','depth':1}
  stale={'entity':'Silla','url':'https://silla.e-oer.com/old.pdf','kind':'pdf','status':'verificada','hash':'old'}
  calls=[]
  def read(r):
   calls.append(r['url']);return dict(resource=r,ok=True,hash='new',details={},kind=r['kind'],text='Docente',children=[fresh] if r['kind']=='page' else [])
  with tempfile.TemporaryDirectory() as t,patch.object(m,'inspect_resource',side_effect=read):
   p=Path(t)/'state.json';m.write_json(p,{'resources':{stale['url']:stale},'pending':{},'gaps_reported':[]})
   m.run({'sources':[root],'max_resources':2},p,t)
  self.assertEqual(calls,[root['url'],fresh['url']])
 def test_initial_inventory_does_not_read_historical_pdfs(self):
  root={'entity':'Silla','url':'https://silla.e-oer.com/root','kind':'page'}
  old_pdf={'entity':'Silla','url':'https://silla.e-oer.com/archive.pdf','kind':'pdf','depth':1}
  calls=[]
  def read(r):
   calls.append(r['url']);return dict(resource=r,ok=True,hash='baseline',details={},kind=r['kind'],text='Taller',children=[old_pdf] if r['kind']=='page' else [])
  with tempfile.TemporaryDirectory() as t,patch.object(m,'inspect_resource',side_effect=read):
   m.run({'sources':[root]},Path(t)/'state.json',t,initialize=True)
   state=json.loads((Path(t)/'state.json').read_text())
  self.assertEqual(calls,[root['url']])
  self.assertEqual(state['resources'][root['url']]['children'],[old_pdf['url']])
  self.assertEqual(state['pending'],{})
 def test_unreachable_host_stops_repeated_downloads(self):
  m.HOST_FAILURES.clear()
  with patch.object(m,'urlopen',side_effect=m.URLError('unreachable')) as fetch,patch.object(m.time,'sleep'):
   for i in range(3):
    with self.assertRaises(RuntimeError):m.fetch('https://labora.gva.es/document'+str(i))
   with self.assertRaisesRegex(RuntimeError,'lectura pendiente'):m.fetch('https://labora.gva.es/next')
   self.assertEqual(fetch.call_count,6)
  m.HOST_FAILURES.clear()
 def test_scan_without_ocr_not_success(self):
  w=PdfWriter();w.add_blank_page(595,842);b=io.BytesIO();w.write(b)
  with patch.object(m.shutil,'which',return_value=None),self.assertRaisesRegex(ValueError,'OCR'):m.extract_pdf(b.getvalue())
 def test_failure_keeps_last_success(self):
  r={'entity':'Silla','url':'https://silla.e-oer.com/test','kind':'pdf'}
  old=dict(r,status='verificada',last_success='yesterday',hash='a')
  record,event=m.transition(old,dict(resource=r,ok=False,error='404'),'today')
  self.assertEqual(record['last_success'],'yesterday');self.assertEqual(event['type'],'fallo_fuente')
 def test_no_repeated_outage_alert(self):
  r={'entity':'Silla','url':'https://silla.e-oer.com/test','kind':'pdf'}
  self.assertIsNone(m.transition(dict(r,status='fallando'),dict(resource=r,ok=False,error='404'),'now')[1])
 def test_no_change_no_alert(self):
  r={'entity':'Silla','url':'https://silla.e-oer.com/test','kind':'pdf'}
  self.assertIsNone(m.transition(dict(r,status='verificada',hash='abc'),dict(resource=r,ok=True,hash='abc',details={},kind='pdf'),'now')[1])
 def test_madrid_schedule(self):
  self.assertTrue(m.scheduled_now(datetime(2026,9,17,6,7,tzinfo=timezone.utc)))
  self.assertFalse(m.scheduled_now(datetime(2026,9,17,3,7,tzinfo=timezone.utc)))
 def test_weekend(self):
  self.assertTrue(m.scheduled_now(datetime(2026,9,19,7,7,tzinfo=timezone.utc)))
  self.assertFalse(m.scheduled_now(datetime(2026,9,19,8,7,tzinfo=timezone.utc)))
 def test_dry_run_and_failed_delivery(self):
  r={'entity':'Silla','url':'https://silla.e-oer.com/test','kind':'pdf'}
  result=dict(resource=r,ok=True,hash='abc',details={},kind='pdf',children=[],text='Docente')
  with tempfile.TemporaryDirectory() as t,patch.object(m,'inspect_resource',return_value=result),patch.object(m,'send_mail') as send:
   m.run({'sources':[r]},Path(t)/'state.json',t);send.assert_not_called()
   send.side_effect=RuntimeError('SMTP down')
   self.assertEqual(m.run({'sources':[r]},Path(t)/'state.json',t,True),2)
   self.assertEqual(len(json.loads((Path(t)/'state.json').read_text())['pending']),1)

class Historical(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from fetch_fixtures import SOURCES
  cls.root=Path(__file__).parent/'fixtures'
 def text(self,n):
  if not (self.root/n).exists():self.skipTest('PDF oficial no disponible: '+n+'; aceptación histórica pendiente')
  return m.extract_pdf((self.root/n).read_bytes())
 def test_alzira_vacancy(self):self.assertIn('IMAI0110',self.text('alzira_puesto.pdf'))
 def test_pdf_regenerated_metadata(self):
  original=(self.root/'alzira_puesto.pdf').read_bytes()
  writer=PdfWriter(clone_from=io.BytesIO(original))
  writer.add_metadata({'/ModDate':'D:20260917180000','/Producer':'Regenerated acceptance fixture'})
  regenerated=io.BytesIO();writer.write(regenerated)
  self.assertNotEqual(original,regenerated.getvalue())
  self.assertEqual(m.normalize(m.extract_pdf(original)),m.normalize(m.extract_pdf(regenerated.getvalue())))
 def test_alzira_deadline(self):
  text=self.text('alzira_calendario.pdf');self.assertIn('ALZIRA',text.upper())
  self.assertTrue(any(d['start']=='2026-09-15' and d['end']=='2026-09-17' for d in m.details(text)['deadlines']))
 def test_silla_april(self):self.assertTrue(any(d['end']=='2026-04-21' for d in m.details(self.text('silla_abril.pdf'))['deadlines']))
 def test_silla_may(self):self.assertTrue(any(d['end']=='2026-05-18' for d in m.details(self.text('silla_mayo.pdf'))['deadlines']))
 def test_silla_change(self):self.assertNotEqual(m.normalize(self.text('silla_abril.pdf')),m.normalize(self.text('silla_mayo.pdf')))
 def test_morella_february(self):self.assertTrue(m.details(self.text('morella_febrero.pdf'))['relative_deadlines'])
 def test_morella_march_urgent(self):
  d=m.details(self.text('morella_marzo.pdf'))
  self.assertTrue(any(__import__('re').search(r'1 dias? habil',x) for x in d['relative_deadlines']));self.assertTrue(d['review_required'])

if __name__=='__main__':unittest.main()

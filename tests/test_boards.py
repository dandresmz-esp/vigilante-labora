import unittest
from unittest.mock import patch
from email.message import Message
import boards

class Response:
 def __init__(self,text):self.data=text.encode();self.headers=Message()
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):return self.data[:n]

class Opener:
 def __init__(self,pages):self.pages=iter(pages);self.requests=[]
 def open(self,request,timeout):self.requests.append(request);return Response(next(self.pages))

class Pagination(unittest.TestCase):
 def test_alzira_two_pages(self):
  opener=Opener(['var TOTAL_LENGTH=2; var PAGINATION=1;<div id="edicto_1">Taller Publicado: hoy</div>', '<div id="edicto_2">Empleo Publicado: ayer</div>'])
  with patch.object(boards,'build_opener',return_value=opener):
   text,children,evidence=boards.collect({'entity':'Alzira','url':'https://sedeelectronica.alzira.es/PortalCiudadano/tablonEdictos.do?formAction=btTablonEdictos'})
  self.assertEqual(evidence['announcements'],2)
  self.assertEqual(len(children),2)
  self.assertIsNone(opener.requests[1].data)
  self.assertIn('st=1',opener.requests[1].full_url)
 def test_alzira_repeated_page_fails(self):
  page='var TOTAL_LENGTH=2; var PAGINATION=1;<div id="edicto_1">Taller Publicado: hoy</div>'
  with patch.object(boards,'build_opener',return_value=Opener([page,page])), self.assertRaisesRegex(ValueError,'incompleta'):
   boards.collect({'entity':'Alzira','url':'https://sedeelectronica.alzira.es/test'})
 def test_silla_two_pages(self):
  first='Página 1 de 2<select name="ctl00$ctl00$cphM$cph$ddlPaginaAnuncios"><option value="0">1</option></select><tr><a href="anuncio.aspx?id=1">Taller</a></tr>'
  second='<tr><a href="anuncio.aspx?id=2">Docente</a></tr>'
  opener=Opener([first,second])
  with patch.object(boards,'build_opener',return_value=opener):
   text,children,evidence=boards.collect({'entity':'Silla','url':'https://silla.sede.dival.es/tablondeanuncios/'})
  self.assertEqual(evidence['announcements'],2)
  self.assertEqual(len(children),2)
  self.assertIn(b'__EVENTTARGET=',opener.requests[1].data)
 def test_silla_empty_page_fails(self):
  with patch.object(boards,'build_opener',return_value=Opener(['Página 1 de 1'])), self.assertRaisesRegex(ValueError,'vacío'):
   boards.collect({'entity':'Silla','url':'https://silla.sede.dival.es/tablondeanuncios/'})

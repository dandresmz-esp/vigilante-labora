import os, unittest
from unittest.mock import patch, MagicMock
from urllib.parse import parse_qs, urlsplit
import monitor as m

class Relay(unittest.TestCase):
 def setUp(self):
  m.HOST_FAILURES.clear(); m.HOST_NEXT.clear()
  self.env=patch.dict(os.environ,{'LABORA_RELAY_URL':'https://vigilante-labora-lector.vigilante-dandresmz-esp.workers.dev/','LABORA_RELAY_TOKEN':'test-only'})
  self.env.start(); self.addCleanup(self.env.stop)
 def test_pdf_and_validators_survive_relay(self):
  response=MagicMock(); response.read.return_value=b'%PDF-test'
  response.headers={'X-Source-URL':'https://labora.gva.es/documents/test','Content-Type':'application/pdf','ETag':'next'}
  opener=MagicMock(); opener.open.return_value.__enter__.return_value=response
  with patch.object(m,'build_opener',return_value=opener):
   data,kind,cache=m.fetch('https://labora.gva.es/documents/test',{'etag':'previous'})
  request=opener.open.call_args.args[0]
  self.assertEqual(parse_qs(urlsplit(request.full_url).query)['url'],['https://labora.gva.es/documents/test'])
  self.assertEqual(request.get_header('Authorization'),'Bearer test-only')
  self.assertEqual(request.get_header('If-none-match'),'previous')
  self.assertEqual((data,kind,cache['etag']),(b'%PDF-test','application/pdf','next'))
 def test_other_sources_never_receive_secret(self):
  response=MagicMock();response.url='https://www.idea-alzira.com/formacion';response.read.return_value=b'page'
  with patch.object(m,'urlopen') as direct:
   direct.return_value.__enter__.return_value=response
   m.fetch(response.url)
  self.assertIsNone(direct.call_args.args[0].get_header('Authorization'))
 def test_untrusted_relay_rejected_before_request(self):
  with patch.dict(os.environ,{'LABORA_RELAY_URL':'https://example.com/'}),patch.object(m,'urlopen') as network:
   with self.assertRaises(ValueError):m.fetch('https://labora.gva.es/documents/test')
  network.assert_not_called()
 def test_redirect_never_forwards_secret(self):
  with self.assertRaises(ValueError):m.NoRelayRedirect().redirect_request(None,None,302,'',{},'https://example.com/')

import unittest
from datetime import date
import monitor as m

class CalendarAlerts(unittest.TestCase):
 def test_calendar_does_not_mix_expired_profile_with_open_deadline(self):
  e={"entity":"LABORA","kind":"pdf","url":"https://labora.gva.es/documents/d/labora/fechas-presen-documen-festa-2026-4-pdf","excerpt":"Escuela taller Elche AGAO0108 del 02/10/2026 al 06/10/2026. Oliva del 16/10/2026 al 20/10/2026", "details":{"codes":["AGAO0108"],"deadlines":[{"start":"2026-10-16","end":"2026-10-20"}]}}
  result=m.classify_event(e,today=date(2026,10,16));self.assertEqual(result["category"],"revisar");self.assertEqual(result["profile_matches"],[]);self.assertEqual(result["active_deadlines"],[])
  e.update(result)
  body=m.mail_body([e],{"finished":"2026-10-16","coverage":{}})
  self.assertNotIn("Coincidencias con tu perfil",body);self.assertNotIn("Plazo detectado",body);self.assertNotIn("plaza",m.mail_subject([e]))
 def test_documents_not_counted_as_vacancies(self):
  self.assertIn("documentos",m.mail_subject([{"category":"revisar"},{"category":"revisar"}]))

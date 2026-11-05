import unittest
import io
import json
import tempfile
from pathlib import Path
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch
import monitor as m


class ProfileReview(unittest.TestCase):
    def hospitality(self, label='Convocatoria docente especialidad hosteleria'):
        return {'entity':'Ontinyent','kind':'pdf','url':'https://example.test/hosteleria',
                'label':label,'excerpt':'Taller de empleo HOTR0208 HOTR0508',
                'details':{'codes':['HOTR0208','HOTR0508'],
                           'deadlines':[{'start':'2026-11-05','end':'2026-11-09'}]}}

    def test_confirmed_hospitality_exclusion(self):
        result = m.classify_event(self.hospitality(), today=date(2026,11,5))
        self.assertEqual(result['reason'], 'especialidad_hosteleria_no_acreditada')
        self.assertFalse(m.deliverable(result))

    def test_support_role_not_excluded_by_hospitality_code(self):
        result = m.classify_event(self.hospitality('Convocatoria docente de apoyo'), today=date(2026,11,5))
        self.assertNotEqual(result.get('reason'), 'especialidad_hosteleria_no_acreditada')

    def test_support_variants_survive_even_with_hospitality_project(self):
        for role in ('Docente apoyo', 'Docent suport', 'Docent reforc', 'Docente de refuerzo'):
            result = m.classify_event(self.hospitality('Convocatoria ' + role), today=date(2026,11,5))
            self.assertNotEqual(result.get('reason'), 'especialidad_hosteleria_no_acreditada')

    def test_mixed_specialties_not_excluded(self):
        event = self.hospitality()
        event['details']['codes'].append('COML0309')
        self.assertNotEqual(m.classify_event(event, today=date(2026,11,5)).get('reason'),
                            'especialidad_hosteleria_no_acreditada')

    def test_calendar_not_notified_but_retained_for_review(self):
        event = {'entity':'LABORA','kind':'pdf','url':'https://labora.gva.es/documents/d/labora/fechas-presen-documen-new',
                 'label':'Calendario','excerpt':'COML0309 en una fila; hosteleria en otra',
                 'details':{'codes':['COML0309','HOTR0508'],'relative_deadlines':['3 dias habiles']}}
        result = m.classify_event(event, today=date(2026,11,5))
        self.assertEqual(result['category'], 'revision_interna')
        self.assertFalse(m.deliverable(result))
        resource = dict(event, status='verificada', hash='version1', review_excerpt=event['excerpt'])
        state = {'resources':{event['url']:resource}}
        with patch.object(m, 'classify_event', return_value=result):
            queue = m.refresh_review_queue(state, '2026-11-05T12:00:00+00:00')
            self.assertIn(event['url'], queue)
            self.assertEqual(queue[event['url']]['details']['codes'], event['details']['codes'])
            m.refresh_review_queue(state, '2026-11-05T13:00:00+00:00')
            self.assertEqual(queue[event['url']]['first_seen'], '2026-11-05T12:00:00+00:00')
        resource['status'] = 'fallando'
        m.refresh_review_queue(state, '2026-11-05T14:00:00+00:00')
        self.assertIn(event['url'], queue)

    def test_failure_still_notified(self):
        self.assertTrue(m.deliverable(m.classify_event({'type':'fallo_fuente'})))

    def test_calendar_persists_and_leaves_no_email_or_action(self):
        resource = {'entity':'LABORA','kind':'pdf',
                    'url':'https://labora.gva.es/documents/d/labora/fechas-presen-documen-fixture',
                    'label':'Calendario de presentacion'}
        text = 'FOTAE/2026/38/46 HOTR0208 Plazo: 3 dias habiles desde la publicacion'
        result = dict(resource=resource, ok=True, hash='abc', details=m.details(text),
                      kind='pdf', children=[], text=text)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m,'inspect_resource',return_value=result), \
             patch.object(m,'send_mail') as send, redirect_stdout(io.StringIO()):
            state_file = Path(tmp)/'state.json'
            state_file.write_text(json.dumps({'version':1,'resources':{},'pending':{},
                                  'gaps_reported':[], 'opportunities':{resource['url']:{'url':resource['url']}}}))
            m.run({'sources':[resource]},state_file,tmp)
            send.assert_not_called()
            data = json.loads((Path(tmp)/'revision_alex.json').read_text())
            self.assertEqual(len(data['items']),1)
            state = json.loads(state_file.read_text())
            self.assertFalse(state['pending'])
            self.assertNotIn(resource['url'],state['opportunities'])
            m.run({'sources':[resource]},state_file,tmp)
            self.assertEqual(len(json.loads((Path(tmp)/'revision_alex.json').read_text())['items']),1)


if __name__ == '__main__':
    unittest.main()

import copy, json, tempfile, unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch
import monitor as m

class RetiredCalendars(unittest.TestCase):
    def setUp(self):
        self.url = 'https://labora.gva.es/documents/d/labora/fechas-presen-documen-fotae-2025-94-pdf'
        self.old = dict(url=self.url, entity='LABORA', kind='pdf', depth=1, label='Calendario', status='fallando', hash='verified', last_success='2026-11-02', error='HTTP Error 404: Not Found', details={'deadlines':[{'end':'2026-10-23'}], 'relative_deadlines':[]})
    def test_expired_detached_verified_404_is_archived(self):
        self.assertTrue(m.retired_labora_calendar(self.old,set(),True,date(2026,11,3)))
    def test_live_or_unread_roots_never_hide_failure(self):
        self.assertFalse(m.retired_labora_calendar(self.old,{self.url},True,date(2026,11,3)))
        self.assertFalse(m.retired_labora_calendar(self.old,set(),False,date(2026,11,3)))
    def test_unknown_future_relative_or_unverified_never_archived(self):
        for change in ({'details':{}},{'details':{'deadlines':[{'end':'2026-11-03'}]}},{'details':{'deadlines':[{'end':'2026-10-23'}],'relative_deadlines':['dos dias']}},{'hash':None},{'last_success':None},{'error':'HTTP Error 503: unavailable'},{'entity':'Carlet'}):
            with self.subTest(change=change):
                r=dict(self.old,**change)
                self.assertFalse(m.retired_labora_calendar(r,set(),True,date(2026,11,3)))
    def test_archival_is_persisted_and_relink_reactivates(self):
        root=dict(entity='LABORA',url='https://labora.gva.es/es/programes-mixtos-d-ocupacio/talleres-de-empleo',kind='page')
        root_record=dict(root,status='verificada',hash='root',children=[])
        calls=[]
        relink=False
        def read(r):
            calls.append(r['url'])
            return dict(resource=r,ok=True,hash='root' if r['kind']=='page' else 'renewed',details={},kind=r['kind'],text='',children=[dict(url=self.url,entity='LABORA',kind='pdf',depth=1,label='Calendario')] if relink and r['kind']=='page' else [])
        with tempfile.TemporaryDirectory() as tmp, patch.object(m,'inspect_resource',side_effect=read):
            state=Path(tmp)/'state.json'
            m.write_json(state,dict(version=1,resources={root['url']:root_record,self.url:self.old},pending={},gaps_reported=[]))
            m.run({'sources':[root]},state,tmp)
            archived=json.loads(state.read_text(encoding='utf-8'))['resources'][self.url]
            self.assertEqual(archived['status'],'historico_retirado')
            self.assertEqual(archived['hash'],'verified')
            self.assertNotIn(self.url,calls)
            report=json.loads((Path(tmp)/'informe.json').read_text(encoding='utf-8'))
            self.assertEqual(report['coverage']['LABORA']['retired_historical'],1)
            calls.clear();relink=True
            m.run({'sources':[root]},state,tmp)
            self.assertIn(self.url,calls)
            self.assertEqual(json.loads(state.read_text(encoding='utf-8'))['resources'][self.url]['status'],'verificada')

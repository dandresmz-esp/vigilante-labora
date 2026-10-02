import unittest

from catalog import approved_projects, opportunity, render_register, render_catalogue


class Register(unittest.TestCase):
    sample = """LISTADO PROYECTOS VALENCIA Estado Ayuda: APROBADOS
FOTAE/2026/10/46
TALLER DE EMPLEO
EMITIDA RESOLUCIÓN APROBATORIA
AJUNTAMENT DE CARLET 962530200
30/12/26 - 29/12/27
LOCALIDAD OBJETO DE ACTUACIÓN GRUPO ESPECIALIDADES ALUMNOS SUBV. MÁXIMA
CARLET
1 ADGG0208 Actividades administrativas en la relación con el cliente 10
1 AGAO0108 Actividades auxiliares en viveros y jardines 10
"""

    def test_project_period_is_not_an_application_deadline(self):
        rows = approved_projects(self.sample,"https://labora.gva.es/list.pdf",{2026})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["id"],"FOTAE/2026/10/46")
        self.assertEqual(rows[0]["entity"],"Ajuntament De Carlet")
        self.assertEqual(rows[0]["project_period"],"30/12/26 – 29/12/27")
        self.assertEqual(rows[0]["application_deadline"],"No publicado en este listado")
        self.assertTrue(rows[0]["profile_match"])

    def test_notice_without_project_code_is_not_falsely_linked(self):
        event={"category":"revisar","entity":"Carlet","url":"https://carlet.sedelectronica.es/board","label":"Convocatoria docente Taller de Empleo","detected_at":"2026-10-02T10:00:00+00:00","details":{}}
        row=opportunity(event)
        self.assertEqual(row["project_id"],"Sin vinculación confirmada")
        self.assertEqual(row["deadline"],"Plazo por confirmar en el anuncio")
        self.assertEqual(row["deadline_end"],"")

    def test_register_cites_official_source_and_keeps_sections_separate(self):
        project=approved_projects(self.sample,"https://labora.gva.es/list.pdf",{2026})[0]
        page=render_catalogue({project["id"]:project},{},"2026-10-02T10:00:00+00:00")
        self.assertIn("FOTAE/2026/10/46",page)
        self.assertIn("No publicado en este listado",page)
        self.assertIn("https://labora.gva.es/list.pdf",page)
        self.assertIn("Convocatorias y plazos detectados",page)

    def test_explicit_project_code_brings_notice_deadline_to_project_row(self):
        project=approved_projects(self.sample,"https://labora.gva.es/list.pdf",{2026})[0]
        notice={"url":"https://carlet.sedelectronica.es/board","project_id":project["id"],
                "entity":"Carlet","title":"Convocatoria docente FOTAE/2026/10/46",
                "deadline":"2026-10-04 a 2026-10-06","deadline_end":"2026-10-06",
                "detected_at":"2026-10-02T10:00:00+00:00","status":"revisar"}
        page=render_catalogue({project["id"]:project},{notice["url"]:notice},"2026-10-02T10:00:00+00:00")
        row=next(line for line in page.splitlines() if line.startswith("| FOTAE/2026/10/46"))
        self.assertIn("2026-10-04 a 2026-10-06",row)
        self.assertIn("https://carlet.sedelectronica.es/board",row)

    def test_action_page_shows_only_open_calls_first(self):
        project=approved_projects(self.sample,"https://labora.gva.es/list.pdf",{2026})[0]
        notice={"url":"https://carlet.sedelectronica.es/board","project_id":project["id"],
                "entity":"Carlet","title":"Convocatoria docente", "deadline":"2026-10-01 a 2026-10-06",
                "deadline_end":"2026-10-06", "detected_at":"2026-10-02T10:00:00+00:00","status":"accion"}
        page=render_register({project["id"]:project},{notice["url"]:notice},"2026-10-02T10:00:00+00:00")
        self.assertIn("## Plazo abierto: presenta la solicitud",page)
        self.assertIn("https://carlet.sedelectronica.es/board",page)
        self.assertNotIn("| FOTAE/2026",page)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from promoters import approved_promoters, board_candidates, verified_board


class PromoterDiscovery(unittest.TestCase):
    def test_approved_valencia_promoter_with_relevant_specialty(self):
        text = ("FOTAE/2026/10/46 AJUNTAMENT DE CARLET 123456789 "
                "AGAO0108 jardineria "
                "FOTAE/2026/11/46 AJUNTAMENT DE CASINOS 123456789 "
                "HOTR0108 hosteleria "
                "FOTAE/2025/12/46 AJUNTAMENT DE CHIVA 123456789 ADG0108")
        self.assertEqual(approved_promoters(text, {2026}),
                         [{"project": "FOTAE/2026/10/46", "name": "carlet"}])

    def test_candidate_hosts_are_official_platforms(self):
        self.assertEqual(board_candidates("Riba-roja de Túria")[0],
                         "https://riba-roja-de-turia.sedelectronica.es/board")

    def test_unverified_page_is_rejected(self):
        class Response:
            status = 200
            url = "https://carlet.sedelectronica.es/board"
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, amount): return b"Carlet - public portal"
        with patch("promoters.urlopen", return_value=Response()):
            self.assertIsNone(verified_board("Carlet"))


if __name__ == "__main__":
    unittest.main()

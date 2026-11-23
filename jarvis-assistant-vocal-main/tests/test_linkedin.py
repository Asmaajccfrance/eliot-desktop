"""Le brouillon LinkedIn s'ouvre rempli, sans clic sur Publier."""
import unittest
from unittest.mock import patch
from urllib.parse import unquote

from tools import linkedin


class BrouillonLinkedInTest(unittest.TestCase):
    def test_louvre_le_composeur_avec_le_texte(self):
        with patch("core.ouvrir_web.ouvrir_url", return_value=True) as ouvrir, \
                patch("core.ouvrir_web.nom_navigateur", return_value="Firefox"):
            resultat = linkedin.rediger_linkedin("Bonjour, voici mon article.")
        url = ouvrir.call_args.args[0]
        self.assertTrue(url.startswith("https://www.linkedin.com/feed/?shareActive=true&text="))
        self.assertIn("Bonjour, voici mon article.", unquote(url))
        self.assertIn("clique toi-meme sur Publier", resultat)

    def test_sans_texte_nouvre_pas_le_navigateur(self):
        with patch("core.ouvrir_web.ouvrir_url") as ouvrir:
            resultat = linkedin.rediger_linkedin("   ")
        ouvrir.assert_not_called()
        self.assertIn("texte", resultat)


if __name__ == "__main__":
    unittest.main()

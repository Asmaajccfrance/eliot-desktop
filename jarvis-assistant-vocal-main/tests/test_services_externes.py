"""Les services ajoutés restent muets sans clé, et PostHog n'envoie rien s'il est éteint."""
import unittest
from unittest.mock import patch

from tools import composio_outils, firecrawl, perplexity
from core import usage


class ServicesExternesTests(unittest.TestCase):
    def test_perplexity_sans_cle(self):
        with patch("tools.perplexity.reglage", return_value=""):
            self.assertIn("pas configuré", perplexity.interroger("météo"))

    def test_firecrawl_refuse_une_adresse_invalide(self):
        with patch("tools.firecrawl.reglage", return_value="cle"):
            self.assertIn("https://", firecrawl.lire("google"))

    def test_composio_sans_cle(self):
        with patch("tools.composio_outils.reglage", return_value=""):
            self.assertIn("pas configuré", composio_outils.lister("linkedin"))

    def test_posthog_eteint_n_envoie_rien(self):
        with patch("core.usage.reglage", return_value=False), \
                patch("core.usage.urllib.request.urlopen") as ouvrir:
            usage.signaler("launch_app", True, 0.1)
        ouvrir.assert_not_called()


if __name__ == "__main__":
    unittest.main()

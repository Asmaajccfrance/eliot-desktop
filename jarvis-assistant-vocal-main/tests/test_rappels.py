"""Rappels vocaux : delai court ou date, sans effacer la liste au redemarrage."""
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from tools import temps


QUAND = datetime(2026, 11, 23, 15, 0)  # lundi


class ResolutionRappelTest(unittest.TestCase):
    def test_dans_dix_minutes(self):
        moment, raison = temps.resoudre_rappel("dans 10 min", maintenant=QUAND)
        self.assertEqual(raison, "")
        self.assertEqual(moment, datetime(2026, 11, 23, 15, 10))

    def test_vendredi_12_a_10h_est_le_prochain_vendredi_12(self):
        moment, raison = temps.resoudre_rappel("vendredi 12 a 10h", maintenant=QUAND)
        self.assertEqual(raison, "")
        self.assertEqual(moment, datetime(2027, 2, 12, 10, 0))
        self.assertEqual(moment.weekday(), 4)

    def test_vendredi_a_10h_est_le_vendredi_qui_vient(self):
        moment, raison = temps.resoudre_rappel("vendredi à 10h", maintenant=QUAND)
        self.assertEqual(moment, datetime(2026, 11, 27, 10, 0))
        self.assertEqual(raison, "")

    def test_sans_heure_demande_l_heure(self):
        moment, raison = temps.resoudre_rappel("vendredi 12", maintenant=QUAND)
        self.assertIsNone(moment)
        self.assertEqual(raison, "heure")


class EnregistrementRappelTest(unittest.TestCase):
    def test_enregistre_la_phrase_et_la_dit_a_l_heure(self):
        with patch.object(temps, "_FICHIER") as fichier, \
                patch.object(temps, "_maintenant", return_value=QUAND), \
                patch.object(temps.voix, "parler") as parler:
            fichier.exists.return_value = False
            ecrit = {}

            def ecrire(texte, encoding="utf-8"):
                ecrit["texte"] = texte

            fichier.write_text.side_effect = ecrire
            reponse = temps.poser_rappel(
                "vous avez rendez-vous avec Paul", quand="dans 10 minutes")
            self.assertIn("Paul", reponse)
            self.assertIn("10 minutes", reponse)
            sauve = json.loads(ecrit["texte"])
            self.assertEqual(sauve[0]["echeance"], "2026-11-23T15:10")
            self.assertEqual(sauve[0]["message"], "Rappel. Vous avez rendez-vous avec Paul")

            fichier.exists.return_value = True
            fichier.read_text.return_value = ecrit["texte"]
            reste = []

            def remplacer(texte, encoding="utf-8"):
                reste.append(texte)

            fichier.write_text.side_effect = remplacer
            with patch.object(temps, "_maintenant", return_value=datetime(2026, 11, 23, 15, 10)):
                temps._sonner_ceux_qui_sont_dus()
            parler.assert_called_once_with("Rappel. Vous avez rendez-vous avec Paul")
            self.assertEqual(json.loads(reste[0]), [])


class RoutageRappelTest(unittest.TestCase):
    def test_un_rdv_ouvre_les_outils_de_temps(self):
        from core.routage_intentions import modules_pour_phrase
        modules = modules_pour_phrase("Vendredi 12 à 10h, rdv")
        self.assertIn("temps", modules)


if __name__ == "__main__":
    unittest.main()

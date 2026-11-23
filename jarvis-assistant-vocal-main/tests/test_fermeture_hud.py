"""Fermer la fenetre du HUD arrete l'ecoute, un simple rechargement non."""
import unittest

import hud


class FermetureFenetreTest(unittest.TestCase):
    def setUp(self):
        hud._CLIENTS.clear()
        hud._FERMETURE = None
        hud._FERMETURE_VUE = False
        if hud._TIMER_FERMETURE is not None:
            hud._TIMER_FERMETURE.cancel()
            hud._TIMER_FERMETURE = None
        self._delai = hud._DELAI_FERMETURE
        hud._DELAI_FERMETURE = 0.05

    def tearDown(self):
        if hud._TIMER_FERMETURE is not None:
            hud._TIMER_FERMETURE.cancel()
            hud._TIMER_FERMETURE = None
        hud._DELAI_FERMETURE = self._delai
        hud._FERMETURE = None
        hud._FERMETURE_VUE = False
        hud._CLIENTS.clear()

    def test_la_fenetre_fermee_coupe_jarvis(self):
        appels = []
        hud.sur_fermeture(lambda: appels.append("stop"))
        hud._CLIENTS.add(object())
        hud._client_arrive()
        hud._CLIENTS.clear()
        hud._client_part()
        timer = hud._TIMER_FERMETURE
        self.assertIsNotNone(timer)
        timer.join(1)
        self.assertEqual(appels, ["stop"])

    def test_un_rechargement_annule_la_coupure(self):
        appels = []
        hud.sur_fermeture(lambda: appels.append("stop"))
        hud._CLIENTS.add(object())
        hud._client_arrive()
        hud._CLIENTS.clear()
        hud._client_part()
        hud._CLIENTS.add(object())
        hud._client_arrive()
        timer = hud._TIMER_FERMETURE
        if timer is not None:
            timer.join(1)
        self.assertEqual(appels, [])


if __name__ == "__main__":
    unittest.main()

import unittest
from fastapi.testclient import TestClient
from backend.main import app

class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def request(self, **overrides):
        payload = dict(term="2027-spring", crn="DEMO-225-A", ticket_at="2026-10-13T12:00:00-05:00")
        payload.update(overrides)
        return self.client.post("/forecast", json=payload)

    def test_demo_contract_and_ticket_endpoint(self):
        r = self.request()
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["demo"])
        self.assertEqual(d["forecast_status"], "available")
        self.assertAlmostEqual(d["probability"], .82 + (.95-.82)/18, places=6)
        self.assertEqual(d["curve"][-1]["at"], d["ticket_at"])
        self.assertEqual(d["curve"][-1]["probability"], d["probability"])

    def test_naive_time_and_prior_ticket_rejected(self):
        self.assertEqual(self.request(ticket_at="2026-10-13T12:00:00").status_code, 422)
        self.assertEqual(self.request(ticket_at="2026-10-12T17:00:00Z").status_code, 422)

    def test_unavailable_and_unknown_sections(self):
        for overrides in [{"crn":"DEMO-341-A"}, {"ticket_at":"2026-11-01T00:00:00Z"}]:
            d = self.request(**overrides).json()
            self.assertEqual(d["forecast_status"], "unavailable")
            self.assertIsNone(d["probability"])
            self.assertEqual(d["curve"], [])
        self.assertEqual(self.request(crn="missing").status_code, 404)

    def test_sections_filter(self):
        self.assertEqual(len(self.client.get("/sections").json()["sections"]),3)
        self.assertEqual(self.client.get("/sections?term=missing").json()["sections"],[])

if __name__ == "__main__":
    unittest.main()

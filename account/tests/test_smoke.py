"""Smoke 테스트 — Django + Ninja 가 부팅되고 기본 경로가 살아 있음을 확인."""

from django.test import Client, TestCase

from account.models import Account


class AccountModelSmokeTests(TestCase):
    def test_create_and_fetch(self):
        Account.objects.create_user(
            username="smoketest",
            password="x",
            name="smoke",
        )
        self.assertTrue(Account.objects.filter(username="smoketest").exists())


class HealthCheckTests(TestCase):
    def test_hc_returns_200(self):
        client = Client()
        response = client.get("/api/hc")
        self.assertEqual(response.status_code, 200)

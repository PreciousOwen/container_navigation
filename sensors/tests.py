import json

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import GPSReading, SensorData


@override_settings(
	SECRET_KEY="test-only-secret-key",
	GPS_DEVICE_API_TOKEN="device-test-secret",
	GPS_MANAGEMENT_API_TOKEN="management-test-secret",
	GPS_PROTOTYPE_DEVICE_ID="GPS-PROTOTYPE-001",
	GPS_LEGACY_INGEST_ENABLED=True,
	GPS_DEVICE_RATE_LIMIT_PER_MINUTE=1000,
	GPS_MANAGEMENT_RATE_LIMIT_PER_MINUTE=1000,
)
class GPSAPITests(TestCase):
	def setUp(self):
		cache.clear()
		self.device_headers = {
			"HTTP_AUTHORIZATION": "Bearer device-test-secret"
		}
		self.management_headers = {
			"HTTP_AUTHORIZATION": "Bearer management-test-secret"
		}
		self.valid_payload = {
			"device_id": "GPS-PROTOTYPE-001",
			"latitude": -6.783814,
			"longitude": 39.198997,
			"recorded_at": "2026-06-28T11:20:00Z",
			"gps_fix": True,
			"satellites": 7,
			"speed_kph": 28.5,
			"heading": 120,
			"battery_percent": 82,
			"signal_strength": 18,
			"sequence_number": 105,
		}

	def post_gps(self, payload=None, **headers):
		return self.client.post(
			reverse("gps_readings"),
			data=json.dumps(payload or self.valid_payload),
			content_type="application/json",
			**(headers or self.device_headers),
		)

	def test_authenticated_post_creates_gps_reading(self):
		response = self.post_gps()

		self.assertEqual(response.status_code, 201)
		self.assertTrue(response.json()["success"])
		self.assertEqual(response.json()["device_id"], "GPS-PROTOTYPE-001")
		reading = GPSReading.objects.get()
		self.assertEqual(str(reading.latitude), "-6.7838140")
		self.assertEqual(reading.sequence_number, 105)

	def test_post_requires_device_token(self):
		response = self.post_gps(**{"HTTP_AUTHORIZATION": "Bearer wrong"})

		self.assertEqual(response.status_code, 401)
		self.assertEqual(GPSReading.objects.count(), 0)

	def test_duplicate_sequence_is_idempotent(self):
		first = self.post_gps()
		second = self.post_gps()

		self.assertEqual(first.status_code, 201)
		self.assertEqual(second.status_code, 200)
		self.assertTrue(second.json()["duplicate"])
		self.assertEqual(first.json()["id"], second.json()["id"])
		self.assertEqual(GPSReading.objects.count(), 1)

	def test_zero_coordinates_are_rejected(self):
		payload = {**self.valid_payload, "latitude": 0, "longitude": 0}
		response = self.post_gps(payload)

		self.assertEqual(response.status_code, 400)
		self.assertIn("no GPS fix", response.json()["message"])

	def test_invalid_optional_ranges_are_rejected(self):
		for field, value in (("battery_percent", 101), ("heading", 361)):
			with self.subTest(field=field):
				payload = {**self.valid_payload, field: value}
				response = self.post_gps(payload)
				self.assertEqual(response.status_code, 400)
		self.assertEqual(GPSReading.objects.count(), 0)

	def test_timestamp_must_include_timezone(self):
		payload = {**self.valid_payload, "recorded_at": "2026-06-28T11:20:00"}
		response = self.post_gps(payload)

		self.assertEqual(response.status_code, 400)
		self.assertIn("timezone", response.json()["message"])

	def test_latest_endpoint_returns_complete_reading(self):
		created = self.post_gps().json()
		response = self.client.get(
			reverse("gps_latest"),
			{"device_id": "GPS-PROTOTYPE-001"},
			**self.management_headers,
		)

		self.assertEqual(response.status_code, 200)
		data = response.json()["data"]
		self.assertEqual(data["id"], created["id"])
		self.assertEqual(data["latitude"], -6.783814)
		self.assertEqual(data["satellites"], 7)
		self.assertTrue(data["recorded_at"].endswith("Z"))

	def test_latest_returns_404_for_unknown_device(self):
		response = self.client.get(
			reverse("gps_latest"),
			{"device_id": "UNKNOWN"},
			**self.management_headers,
		)

		self.assertEqual(response.status_code, 404)

	def test_history_filters_after_id_and_reports_more(self):
		ids = []
		for sequence in range(1, 4):
			payload = {**self.valid_payload, "sequence_number": sequence}
			ids.append(self.post_gps(payload).json()["id"])

		response = self.client.get(
			reverse("gps_readings"),
			{
				"device_id": "GPS-PROTOTYPE-001",
				"after_id": ids[0],
				"limit": 1,
			},
			**self.management_headers,
		)

		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertEqual([row["id"] for row in body["results"]], [ids[1]])
		self.assertEqual(body["last_id"], ids[1])
		self.assertTrue(body["has_more"])

	def test_history_requires_management_token(self):
		response = self.client.get(
			reverse("gps_readings"),
			{"device_id": "GPS-PROTOTYPE-001"},
		)

		self.assertEqual(response.status_code, 401)

	def test_valid_legacy_post_is_mirrored(self):
		response = self.client.post(
			reverse("sensor_data"),
			data=json.dumps({"gps_location": "-6.783814,39.198997"}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()["gps_accepted"])
		self.assertEqual(SensorData.objects.count(), 1)
		reading = GPSReading.objects.get()
		self.assertEqual(reading.device_id, "GPS-PROTOTYPE-001")

	def test_invalid_legacy_fix_is_retained_raw_but_not_mirrored(self):
		response = self.client.post(
			reverse("sensor_data"),
			data=json.dumps({"gps_location": "0.000000,0.000000"}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.json()["gps_accepted"])
		self.assertEqual(SensorData.objects.count(), 1)
		self.assertEqual(GPSReading.objects.count(), 0)

	def test_monitoring_page_shows_valid_gps_reading(self):
		self.post_gps()
		response = self.client.get(reverse("sensor_data"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "GPS-PROTOTYPE-001")
		self.assertContains(response, "Latest Valid GPS Readings")


@override_settings(
	SECRET_KEY="test-only-secret-key",
	GPS_DEVICE_API_TOKEN="",
)
class GPSAPIConfigurationTests(TestCase):
	def test_api_fails_closed_when_device_token_is_not_configured(self):
		response = self.client.post(
			reverse("gps_readings"),
			data="{}",
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 503)

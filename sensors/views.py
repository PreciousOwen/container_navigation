import json
import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from .models import GPSReading, SensorData


LEGACY_SEQUENCE_OFFSET = 9_000_000_000_000_000


def _json_error(message: str, status: int) -> JsonResponse:
	return JsonResponse({"success": False, "message": message}, status=status)


def _read_json_body(request: HttpRequest):
	raw_body = request.body.decode("utf-8", errors="replace").strip()
	if not raw_body:
		return None, _json_error("Empty request body", 400)

	try:
		payload = json.loads(raw_body)
	except json.JSONDecodeError as exc:
		return None, _json_error(f"Invalid JSON: {exc.msg}", 400)

	if not isinstance(payload, dict):
		return None, _json_error("The JSON body must be an object", 400)
	return payload, None


def _bearer_token_is_valid(request: HttpRequest, expected_token: str) -> bool:
	header = request.headers.get("Authorization", "")
	prefix = "Bearer "
	if not expected_token or not header.startswith(prefix):
		return False
	return secrets.compare_digest(header[len(prefix):].strip(), expected_token)


def _authenticate(request: HttpRequest, expected_token: str, label: str):
	if not expected_token:
		return _json_error(f"{label} API token is not configured", 503)
	if not _bearer_token_is_valid(request, expected_token):
		return _json_error(f"Invalid {label.lower()} token", 401)
	return None


def _rate_limit(request: HttpRequest, scope: str, limit: int):
	"""Small fixed-window limiter suitable for this single-device prototype."""
	client_ip = request.META.get("HTTP_X_REAL_IP") or request.META.get(
		"REMOTE_ADDR", "unknown"
	)
	minute = timezone.now().strftime("%Y%m%d%H%M")
	key = f"gps-rate:{scope}:{client_ip}:{minute}"
	if cache.add(key, 1, timeout=70):
		return None
	try:
		count = cache.incr(key)
	except ValueError:
		cache.set(key, 1, timeout=70)
		count = 1
	if count > limit:
		response = _json_error("Rate limit exceeded", 429)
		response["Retry-After"] = "60"
		return response
	return None


def _decimal_value(payload: dict, field: str, *, required=False):
	value = payload.get(field)
	if value in (None, ""):
		if required:
			raise ValueError(f"{field} is required")
		return None
	if isinstance(value, bool):
		raise ValueError(f"{field} must be numeric")
	try:
		parsed = Decimal(str(value))
	except (InvalidOperation, ValueError):
		raise ValueError(f"{field} must be numeric") from None
	if not parsed.is_finite():
		raise ValueError(f"{field} must be a finite number")
	return parsed


def _integer_value(payload: dict, field: str, *, required=False):
	value = payload.get(field)
	if value in (None, ""):
		if required:
			raise ValueError(f"{field} is required")
		return None
	if isinstance(value, bool):
		raise ValueError(f"{field} must be an integer")
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		raise ValueError(f"{field} must be an integer") from None
	if str(value).strip() not in {str(parsed), f"+{parsed}"}:
		raise ValueError(f"{field} must be an integer")
	return parsed


def _coordinates_from_payload(payload: dict):
	if "gps_location" in payload and (
		"latitude" not in payload or "longitude" not in payload
	):
		parts = str(payload.get("gps_location", "")).split(",")
		if len(parts) != 2:
			raise ValueError("gps_location must contain latitude,longitude")
		candidate = dict(payload)
		candidate["latitude"] = parts[0].strip()
		candidate["longitude"] = parts[1].strip()
		payload = candidate

	latitude = _decimal_value(payload, "latitude", required=True)
	longitude = _decimal_value(payload, "longitude", required=True)
	if latitude < Decimal("-90") or latitude > Decimal("90"):
		raise ValueError("Latitude must be between -90 and 90")
	if longitude < Decimal("-180") or longitude > Decimal("180"):
		raise ValueError("Longitude must be between -180 and 180")
	if latitude == 0 and longitude == 0:
		raise ValueError("Invalid GPS coordinates: 0,0 means no GPS fix")
	return latitude, longitude


def _validate_gps_payload(payload: dict):
	device_id = str(payload.get("device_id", "")).strip()
	if not device_id:
		raise ValueError("device_id is required")
	if len(device_id) > 50:
		raise ValueError("device_id cannot exceed 50 characters")
	if payload.get("gps_fix") is not True:
		raise ValueError("gps_fix must be true")

	latitude, longitude = _coordinates_from_payload(payload)
	recorded_at_raw = payload.get("recorded_at")
	if not isinstance(recorded_at_raw, str):
		raise ValueError("recorded_at is required")
	recorded_at = parse_datetime(recorded_at_raw)
	if recorded_at is None or not timezone.is_aware(recorded_at):
		raise ValueError("recorded_at must be an ISO 8601 timestamp with timezone")

	sequence_number = _integer_value(payload, "sequence_number", required=True)
	if sequence_number < 0:
		raise ValueError("sequence_number cannot be negative")
	if sequence_number >= LEGACY_SEQUENCE_OFFSET:
		raise ValueError("sequence_number is outside the supported range")

	satellites = _integer_value(payload, "satellites")
	if satellites is not None and not 0 <= satellites <= 255:
		raise ValueError("satellites must be between 0 and 255")

	speed_kph = _decimal_value(payload, "speed_kph")
	if speed_kph is not None and speed_kph < 0:
		raise ValueError("speed_kph cannot be negative")

	heading = _decimal_value(payload, "heading")
	if heading is not None and not Decimal("0") <= heading <= Decimal("360"):
		raise ValueError("heading must be between 0 and 360")

	battery_percent = _integer_value(payload, "battery_percent")
	if battery_percent is not None and not 0 <= battery_percent <= 100:
		raise ValueError("battery_percent must be between 0 and 100")

	signal_strength = _integer_value(payload, "signal_strength")

	return {
		"device_id": device_id,
		"latitude": latitude,
		"longitude": longitude,
		"recorded_at": recorded_at,
		"gps_fix": True,
		"satellites": satellites,
		"speed_kph": speed_kph,
		"heading": heading,
		"battery_percent": battery_percent,
		"signal_strength": signal_strength,
		"sequence_number": sequence_number,
		"raw_payload": payload,
	}


def _isoformat(value):
	return value.isoformat().replace("+00:00", "Z") if value else None


def _serialize_reading(reading: GPSReading, *, compact=False):
	data = {
		"id": reading.id,
		"device_id": reading.device_id,
		"latitude": float(reading.latitude),
		"longitude": float(reading.longitude),
		"recorded_at": _isoformat(reading.recorded_at),
		"received_at": _isoformat(reading.received_at),
	}
	if not compact:
		data.update(
			{
				"gps_fix": reading.gps_fix,
				"satellites": reading.satellites,
				"speed_kph": (
					float(reading.speed_kph)
					if reading.speed_kph is not None
					else None
				),
				"heading": (
					float(reading.heading) if reading.heading is not None else None
				),
				"battery_percent": reading.battery_percent,
				"signal_strength": reading.signal_strength,
				"sequence_number": reading.sequence_number,
			}
		)
	return data


def _mirror_legacy_gps(entry: SensorData):
	if not settings.GPS_LEGACY_INGEST_ENABLED:
		return None
	payload = entry.payload
	if not isinstance(payload, dict) or "gps_location" not in payload:
		return None
	try:
		latitude, longitude = _coordinates_from_payload(payload)
	except ValueError:
		return None

	device_id = str(
		payload.get("device_id")
		or payload.get("sensor_id")
		or settings.GPS_PROTOTYPE_DEVICE_ID
	).strip()[:50]
	reading, _ = GPSReading.objects.get_or_create(
		device_id=device_id,
		sequence_number=LEGACY_SEQUENCE_OFFSET + entry.id,
		defaults={
			"latitude": latitude,
			"longitude": longitude,
			"recorded_at": entry.received_at,
			"gps_fix": True,
			"raw_payload": payload,
		},
	)
	return reading


@csrf_exempt
def sensor_data(request: HttpRequest):
	"""Legacy raw sensor receiver and human-readable monitoring page."""
	if request.method == "POST":
		payload, error = _read_json_body(request)
		if error:
			return error
		entry = SensorData.objects.create(payload=payload)
		gps_reading = _mirror_legacy_gps(entry)
		response = {"success": True, "id": entry.id}
		if "gps_location" in payload:
			response["gps_accepted"] = gps_reading is not None
			if gps_reading:
				response["gps_reading_id"] = gps_reading.id
		# Preserve the legacy endpoint's original HTTP 200 contract.
		return JsonResponse(response)
	if request.method != "GET":
		return _json_error("Method not allowed", 405)

	entries = SensorData.objects.all()[:200]
	rendered_entries = [
		{
			"id": entry.id,
			"received_at": entry.received_at,
			"payload_pretty": json.dumps(
				entry.payload, indent=2, sort_keys=True, ensure_ascii=False
			),
		}
		for entry in entries
	]
	return render(
		request,
		"sensors/sensor_data.html",
		{
			"entries": rendered_entries,
			"gps_readings": GPSReading.objects.all()[:20],
			"legacy_ingest_enabled": settings.GPS_LEGACY_INGEST_ENABLED,
		},
	)


@csrf_exempt
def gps_readings(request: HttpRequest):
	if request.method == "POST":
		error = _authenticate(request, settings.GPS_DEVICE_API_TOKEN, "Device")
		if error:
			return error
		error = _rate_limit(
			request, "device", settings.GPS_DEVICE_RATE_LIMIT_PER_MINUTE
		)
		if error:
			return error
		payload, error = _read_json_body(request)
		if error:
			return error
		try:
			validated = _validate_gps_payload(payload)
		except ValueError as exc:
			return _json_error(str(exc), 400)

		try:
			reading, created = GPSReading.objects.get_or_create(
				device_id=validated["device_id"],
				sequence_number=validated["sequence_number"],
				defaults={
					key: value
					for key, value in validated.items()
					if key not in {"device_id", "sequence_number"}
				},
			)
		except IntegrityError:
			reading = GPSReading.objects.get(
				device_id=validated["device_id"],
				sequence_number=validated["sequence_number"],
			)
			created = False

		response = {
			"success": True,
			"id": reading.id,
			"device_id": reading.device_id,
			"received_at": _isoformat(reading.received_at),
		}
		if not created:
			response["duplicate"] = True
		return JsonResponse(response, status=201 if created else 200)

	if request.method == "GET":
		error = _authenticate(
			request, settings.GPS_MANAGEMENT_API_TOKEN, "Management"
		)
		if error:
			return error
		error = _rate_limit(
			request, "management", settings.GPS_MANAGEMENT_RATE_LIMIT_PER_MINUTE
		)
		if error:
			return error

		device_id = request.GET.get("device_id", "").strip()
		if not device_id:
			return _json_error("device_id is required", 400)
		try:
			after_id = int(request.GET.get("after_id", "0"))
			limit = int(request.GET.get("limit", "100"))
		except ValueError:
			return _json_error("after_id and limit must be integers", 400)
		if after_id < 0:
			return _json_error("after_id cannot be negative", 400)
		if not 1 <= limit <= 500:
			return _json_error("limit must be between 1 and 500", 400)

		rows = list(
			GPSReading.objects.filter(
				device_id=device_id, id__gt=after_id, gps_fix=True
			).order_by("id")[: limit + 1]
		)
		has_more = len(rows) > limit
		rows = rows[:limit]
		return JsonResponse(
			{
				"success": True,
				"results": [
					_serialize_reading(row, compact=True) for row in rows
				],
				"last_id": rows[-1].id if rows else after_id,
				"has_more": has_more,
			}
		)

	return _json_error("Method not allowed", 405)


def gps_latest(request: HttpRequest):
	if request.method != "GET":
		return _json_error("Method not allowed", 405)
	error = _authenticate(request, settings.GPS_MANAGEMENT_API_TOKEN, "Management")
	if error:
		return error
	error = _rate_limit(
		request, "management", settings.GPS_MANAGEMENT_RATE_LIMIT_PER_MINUTE
	)
	if error:
		return error

	device_id = request.GET.get("device_id", "").strip()
	if not device_id:
		return _json_error("device_id is required", 400)
	reading = (
		GPSReading.objects.filter(device_id=device_id, gps_fix=True)
		.order_by("-id")
		.first()
	)
	if reading is None:
		return _json_error("No valid GPS reading found for this device", 404)
	return JsonResponse({"success": True, "data": _serialize_reading(reading)})

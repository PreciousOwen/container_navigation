import json

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import SensorData


@csrf_exempt
def sensor_data(request: HttpRequest):
	if request.method == "POST":
		raw_body = request.body.decode("utf-8", errors="replace").strip()
		if not raw_body:
			return JsonResponse(
				{"success": False, "error": "Empty request body"}, status=400
			)

		try:
			payload = json.loads(raw_body)
		except json.JSONDecodeError as exc:
			return JsonResponse(
				{"success": False, "error": f"Invalid JSON: {exc.msg}"},
				status=400,
			)

		entry = SensorData.objects.create(payload=payload)
		return JsonResponse({"success": True, "id": entry.id})

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
		{"entries": rendered_entries},
	)

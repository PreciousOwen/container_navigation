from django.contrib import admin

from .models import GPSReading, SensorData


@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
	list_display = ("id", "received_at")
	readonly_fields = ("received_at",)
	ordering = ("-id",)


@admin.register(GPSReading)
class GPSReadingAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"device_id",
		"latitude",
		"longitude",
		"recorded_at",
		"received_at",
		"gps_fix",
	)
	list_filter = ("device_id", "gps_fix")
	search_fields = ("device_id",)
	readonly_fields = ("received_at", "raw_payload")
	ordering = ("-id",)

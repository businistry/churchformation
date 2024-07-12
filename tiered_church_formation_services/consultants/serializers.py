## consultants/serializers.py

from rest_framework import serializers
from .models import Consultant, Appointment, ConsultantRating, ConsultantAvailability
from users.serializers import UserSerializer
from services.serializers import ClientProjectSerializer

class ConsultantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    average_rating = serializers.FloatField(read_only=True)

    class Meta:
        model = Consultant
        fields = ['id', 'user', 'specialization', 'bio', 'hourly_rate', 'is_available', 'created_at', 'updated_at', 'average_rating']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['average_rating'] = instance.ratings.aggregate(avg_rating=models.Avg('rating'))['avg_rating'] or 0
        return representation

class AppointmentSerializer(serializers.ModelSerializer):
    consultant = ConsultantSerializer(read_only=True)
    project = ClientProjectSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = ['id', 'consultant', 'project', 'start_time', 'end_time', 'status', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time.")
        return data

class ConsultantRatingSerializer(serializers.ModelSerializer):
    client = UserSerializer(read_only=True)

    class Meta:
        model = ConsultantRating
        fields = ['id', 'consultant', 'client', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'consultant', 'client', 'created_at']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

class ConsultantAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultantAvailability
        fields = ['id', 'consultant', 'day_of_week', 'start_time', 'end_time']
        read_only_fields = ['id', 'consultant']

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time.")
        return data

class ConsultantDetailSerializer(ConsultantSerializer):
    availabilities = ConsultantAvailabilitySerializer(many=True, read_only=True)
    ratings = ConsultantRatingSerializer(many=True, read_only=True)

    class Meta(ConsultantSerializer.Meta):
        fields = ConsultantSerializer.Meta.fields + ['availabilities', 'ratings']

class AppointmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['consultant', 'project', 'start_time', 'end_time', 'notes']

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time.")
        
        # Check for overlapping appointments
        overlapping_appointments = Appointment.objects.filter(
            consultant=data['consultant'],
            start_time__lt=data['end_time'],
            end_time__gt=data['start_time']
        )
        if overlapping_appointments.exists():
            raise serializers.ValidationError("This time slot is already booked.")
        
        return data

class ConsultantSearchSerializer(serializers.Serializer):
    specialization = serializers.CharField(required=False, allow_blank=True)
    min_rating = serializers.FloatField(required=False, min_value=0, max_value=5)
    max_hourly_rate = serializers.DecimalField(required=False, max_digits=6, decimal_places=2, min_value=0)

class ConsultantStatsSerializer(serializers.Serializer):
    total_appointments = serializers.IntegerField()
    completed_appointments = serializers.IntegerField()
    average_rating = serializers.FloatField()

class AppointmentCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)

class AppointmentCompleteSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)

class ConsultantUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultant
        fields = ['specialization', 'bio', 'hourly_rate', 'is_available']

    def validate_hourly_rate(self, value):
        if value < 0:
            raise serializers.ValidationError("Hourly rate cannot be negative.")
        return value

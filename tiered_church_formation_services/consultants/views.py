## consultants/views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Avg
from django.utils import timezone
from .models import Consultant, Appointment, ConsultantRating, ConsultantAvailability
from .serializers import (
    ConsultantSerializer,
    AppointmentSerializer,
    ConsultantRatingSerializer,
    ConsultantAvailabilitySerializer
)
from services.models import ClientProject
from django.core.exceptions import ValidationError
from django.db import transaction

class ConsultantListView(generics.ListAPIView):
    queryset = Consultant.objects.all()
    serializer_class = ConsultantSerializer
    permission_classes = [permissions.IsAuthenticated]

class ConsultantDetailView(generics.RetrieveAPIView):
    queryset = Consultant.objects.all()
    serializer_class = ConsultantSerializer
    permission_classes = [permissions.IsAuthenticated]

class AppointmentListCreateView(generics.ListCreateAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'consultant_profile'):
            return Appointment.objects.filter(consultant=user.consultant_profile)
        return Appointment.objects.filter(project__client=user)

    def perform_create(self, serializer):
        consultant = get_object_or_404(Consultant, pk=self.request.data.get('consultant'))
        project = get_object_or_404(ClientProject, pk=self.request.data.get('project'), client=self.request.user)
        
        start_time = serializer.validated_data['start_time']
        end_time = serializer.validated_data['end_time']

        # Check consultant availability
        if not ConsultantAvailability.objects.filter(
            consultant=consultant,
            day_of_week=start_time.weekday(),
            start_time__lte=start_time.time(),
            end_time__gte=end_time.time()
        ).exists():
            raise ValidationError("The consultant is not available at this time.")

        # Check for overlapping appointments
        if Appointment.objects.filter(
            consultant=consultant,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists():
            raise ValidationError("This time slot is already booked.")

        serializer.save(consultant=consultant, project=project)

class AppointmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'consultant_profile'):
            return Appointment.objects.filter(consultant=user.consultant_profile)
        return Appointment.objects.filter(project__client=user)

class AppointmentCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        
        if appointment.project.client != request.user and appointment.consultant.user != request.user:
            return Response({"error": "You don't have permission to cancel this appointment."},
                            status=status.HTTP_403_FORBIDDEN)

        if appointment.status not in ['scheduled', 'in_progress']:
            return Response({"error": "This appointment cannot be cancelled."},
                            status=status.HTTP_400_BAD_REQUEST)

        appointment.cancel()
        return Response({"message": "Appointment cancelled successfully."},
                        status=status.HTTP_200_OK)

class AppointmentCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        
        if appointment.consultant.user != request.user:
            return Response({"error": "Only the consultant can mark an appointment as completed."},
                            status=status.HTTP_403_FORBIDDEN)

        if appointment.status != 'in_progress':
            return Response({"error": "Only in-progress appointments can be marked as completed."},
                            status=status.HTTP_400_BAD_REQUEST)

        appointment.complete()
        return Response({"message": "Appointment marked as completed successfully."},
                        status=status.HTTP_200_OK)

class ConsultantRatingCreateView(generics.CreateAPIView):
    serializer_class = ConsultantRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        consultant = get_object_or_404(Consultant, pk=self.kwargs['pk'])
        if not Appointment.objects.filter(consultant=consultant, project__client=self.request.user, status='completed').exists():
            raise ValidationError("You can only rate consultants after completing an appointment with them.")
        serializer.save(consultant=consultant, client=self.request.user)

class ConsultantRatingListView(generics.ListAPIView):
    serializer_class = ConsultantRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        consultant = get_object_or_404(Consultant, pk=self.kwargs['pk'])
        return ConsultantRating.objects.filter(consultant=consultant)

class ConsultantAvailabilityListCreateView(generics.ListCreateAPIView):
    serializer_class = ConsultantAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        consultant = get_object_or_404(Consultant, pk=self.kwargs['pk'])
        return ConsultantAvailability.objects.filter(consultant=consultant)

    def perform_create(self, serializer):
        consultant = get_object_or_404(Consultant, pk=self.kwargs['pk'])
        if consultant.user != self.request.user:
            raise ValidationError("You can only set availability for your own consultant profile.")
        serializer.save(consultant=consultant)

class ConsultantAvailabilityDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ConsultantAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ConsultantAvailability.objects.filter(consultant__user=self.request.user)

class ConsultantStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        consultant = get_object_or_404(Consultant, pk=pk)
        stats = {
            'total_appointments': Appointment.objects.filter(consultant=consultant).count(),
            'completed_appointments': Appointment.objects.filter(consultant=consultant, status='completed').count(),
            'average_rating': ConsultantRating.objects.filter(consultant=consultant).aggregate(Avg('rating'))['rating__avg']
        }
        return Response(stats)

class UpcomingAppointmentsView(generics.ListAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()
        if hasattr(user, 'consultant_profile'):
            return Appointment.objects.filter(consultant=user.consultant_profile, start_time__gt=now, status='scheduled')
        return Appointment.objects.filter(project__client=user, start_time__gt=now, status='scheduled')

class ConsultantSearchView(generics.ListAPIView):
    serializer_class = ConsultantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Consultant.objects.all()
        specialization = self.request.query_params.get('specialization', None)
        if specialization:
            queryset = queryset.filter(specialization__icontains=specialization)
        return queryset

class ConsultantUpdateView(generics.UpdateAPIView):
    serializer_class = ConsultantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_object_or_404(Consultant, user=self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            consultant = serializer.save()
            if 'is_available' in serializer.validated_data:
                is_available = serializer.validated_data['is_available']
                upcoming_appointments = Appointment.objects.filter(
                    consultant=consultant,
                    start_time__gt=timezone.now(),
                    status='scheduled'
                )
                if not is_available:
                    upcoming_appointments.update(status='cancelled')

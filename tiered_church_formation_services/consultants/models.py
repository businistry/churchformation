## consultants/models.py

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone

class Consultant(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='consultant_profile')
    specialization = models.CharField(max_length=100)
    bio = models.TextField()
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.specialization}"

    class Meta:
        ordering = ['user__last_name', 'user__first_name']

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE, related_name='appointments')
    project = models.ForeignKey('services.ClientProject', on_delete=models.CASCADE, related_name='appointments')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.consultant} - {self.project} ({self.start_time})"

    def schedule(self):
        if self.status == 'cancelled':
            self.status = 'scheduled'
            self.save()

    def cancel(self):
        if self.status in ['scheduled', 'in_progress']:
            self.status = 'cancelled'
            self.save()

    def complete(self):
        if self.status == 'in_progress':
            self.status = 'completed'
            self.save()

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")
        if self.start_time < timezone.now():
            raise ValidationError("Cannot schedule appointments in the past.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['consultant', 'start_time']),
            models.Index(fields=['project', 'start_time']),
            models.Index(fields=['status']),
        ]

class ConsultantRating(models.Model):
    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE, related_name='ratings')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='consultant_ratings')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MinValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client} rated {self.consultant}: {self.rating}"

    class Meta:
        unique_together = ['consultant', 'client']
        ordering = ['-created_at']

class ConsultantAvailability(models.Model):
    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(7)])
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.consultant} - {self.get_day_of_week_display()} ({self.start_time} - {self.end_time})"

    class Meta:
        unique_together = ['consultant', 'day_of_week']
        ordering = ['day_of_week', 'start_time']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

## services/models.py

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone

class ServiceTier(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_full_service = models.BooleanField(default=False)
    features = models.JSONField(default=list)

    def __str__(self):
        return self.name

class ClientProject(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='projects')
    service_tier = models.ForeignKey(ServiceTier, on_delete=models.PROTECT, related_name='projects')
    project_name = models.CharField(max_length=255)
    start_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.project_name} - {self.client.email}"

    def start_project(self):
        if self.status == 'pending':
            self.status = 'in_progress'
            self.start_date = timezone.now()
            self.save()

    def update_progress(self, step: str, status: str):
        self.progress[step] = status
        self.save()

    def complete_project(self):
        if self.status == 'in_progress':
            self.status = 'completed'
            self.save()

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stripe_charge_id = models.CharField(max_length=100, unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Payment of ${self.amount} by {self.user.email}"

    def process_payment(self):
        # This method would integrate with Stripe to process the payment
        # For now, we'll just mark it as completed
        self.status = 'completed'
        self.save()

    def refund(self):
        # This method would integrate with Stripe to process the refund
        # For now, we'll just mark it as refunded
        if self.status == 'completed':
            self.status = 'refunded'
            self.save()

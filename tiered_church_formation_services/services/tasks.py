## services/tasks.py

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.db import models
from .models import ClientProject, Payment
import stripe
import logging

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

@shared_task
def process_payment_task(project_id: int) -> None:
    """
    Process payment for a client project.
    """
    try:
        project = ClientProject.objects.select_related('client').get(id=project_id)
        payment = Payment.objects.get(user=project.client, stripe_charge_id=f"temp_{project.id}")

        if not hasattr(project.client, 'stripe_customer_id') or not project.client.stripe_customer_id:
            raise ValueError("Stripe customer ID not found for the user.")

        # Create a Stripe charge
        charge = stripe.Charge.create(
            amount=int(payment.amount * 100),  # Amount in cents
            currency="usd",
            customer=project.client.stripe_customer_id,
            description=f"Payment for project: {project.project_name}"
        )

        # Update payment status
        payment.stripe_charge_id = charge.id
        payment.status = 'completed'
        payment.save()

        # Start the project
        project.start_project()

        # Send confirmation email
        send_mail(
            subject="Payment Processed Successfully",
            message=f"Your payment of ${payment.amount} for project '{project.project_name}' has been processed successfully.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[project.client.email],
            fail_silently=False,
        )

    except ClientProject.DoesNotExist:
        logger.error(f"ClientProject with id {project_id} does not exist.")
    except Payment.DoesNotExist:
        logger.error(f"Payment for project {project_id} does not exist.")
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        # Handle the error (e.g., mark payment as failed, notify the user)
    except Exception as e:
        logger.error(f"Unexpected error in process_payment_task: {str(e)}")

@shared_task
def update_project_status_task(project_id: int) -> None:
    """
    Update the status of a client project based on its progress.
    """
    try:
        project = ClientProject.objects.select_related('client').get(id=project_id)
        total_steps = len(project.progress)
        completed_steps = sum(1 for status in project.progress.values() if status == 'completed')

        if total_steps > 0:
            if completed_steps == total_steps:
                project.complete_project()
                
                # Send project completion email
                send_mail(
                    subject="Project Completed",
                    message=f"Your project '{project.project_name}' has been completed successfully.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[project.client.email],
                    fail_silently=False,
                )
        else:
            logger.warning(f"Project {project_id} has no progress steps defined.")

    except ClientProject.DoesNotExist:
        logger.error(f"ClientProject with id {project_id} does not exist.")
    except Exception as e:
        logger.error(f"Unexpected error in update_project_status_task: {str(e)}")

@shared_task
def send_project_reminders() -> None:
    """
    Send reminders for projects that haven't been updated in a while.
    """
    threshold_days = 7  # Number of days since last update to trigger a reminder
    threshold_date = timezone.now() - timezone.timedelta(days=threshold_days)

    projects_to_remind = ClientProject.objects.filter(
        status='in_progress',
        start_date__lte=threshold_date
    ).select_related('client')

    for project in projects_to_remind:
        send_mail(
            subject="Project Update Reminder",
            message=f"This is a friendly reminder to update your project '{project.project_name}'. It's been {threshold_days} days since your last update.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[project.client.email],
            fail_silently=False,
        )

@shared_task
def clean_pending_payments() -> None:
    """
    Clean up pending payments that are older than a certain threshold.
    """
    threshold_hours = 24  # Number of hours after which pending payments should be cleaned up
    threshold_date = timezone.now() - timezone.timedelta(hours=threshold_hours)

    pending_payments = Payment.objects.filter(
        status='pending',
        timestamp__lte=threshold_date
    ).select_related('user')

    for payment in pending_payments:
        # Cancel the associated project
        ClientProject.objects.filter(client=payment.user, status='pending').update(status='cancelled')

        # Delete the pending payment
        payment.delete()

        # Notify the user
        send_mail(
            subject="Payment Cancelled",
            message=f"Your pending payment of ${payment.amount} has been cancelled due to inactivity.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.user.email],
            fail_silently=False,
        )

@shared_task
def generate_monthly_report() -> None:
    """
    Generate a monthly report of completed projects and revenue.
    """
    last_month = timezone.now().replace(day=1) - timezone.timedelta(days=1)
    start_date = last_month.replace(day=1)
    end_date = timezone.now().replace(day=1)

    completed_projects = ClientProject.objects.filter(
        status='completed',
        start_date__gte=start_date,
        start_date__lt=end_date
    ).select_related('client')

    total_revenue = Payment.objects.filter(
        status='completed',
        timestamp__gte=start_date,
        timestamp__lt=end_date
    ).aggregate(total=models.Sum('amount'))['total'] or 0

    report = f"Monthly Report ({start_date.strftime('%B %Y')})\n\n"
    report += f"Completed Projects: {completed_projects.count()}\n"
    report += f"Total Revenue: ${total_revenue}\n\n"
    report += "Project Details:\n"

    for project in completed_projects:
        report += f"- {project.project_name} (Client: {project.client.email})\n"

    # Send report to administrators
    send_mail(
        subject=f"Monthly Report - {start_date.strftime('%B %Y')}",
        message=report,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[admin[1] for admin in settings.ADMINS],
        fail_silently=False,
    )

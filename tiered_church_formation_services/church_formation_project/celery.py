## church_formation_project/celery.py

import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'church_formation_project.settings')

# Create a new Celery app
app = Celery('church_formation_project')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@app.task(bind=True)
def debug_task(self):
    """
    A debug task that can be used to test Celery configuration.
    """
    print(f'Request: {self.request!r}')

# Configure Celery beat schedule
app.conf.beat_schedule = {
    'check-appointment-reminders': {
        'task': 'consultants.tasks.send_appointment_reminders',
        'schedule': 3600.0,  # Run every hour
    },
    'update-project-statuses': {
        'task': 'services.tasks.update_project_statuses',
        'schedule': 86400.0,  # Run daily
    },
}

# Optional configuration, see the application user guide.
app.conf.update(
    result_expires=3600,  # Results expire after 1 hour
    worker_prefetch_multiplier=1,  # Disable prefetching for more predictable task execution
    task_acks_late=True,  # Tasks are acknowledged after the task has been executed
    task_reject_on_worker_lost=True,  # Reject tasks if the worker connection is lost
    task_serializer='json',
    accept_content=['json'],  # Ignore other content
    result_serializer='json',
    timezone=settings.TIME_ZONE,
    enable_utc=True,
)

# Define routing for specific tasks
app.conf.task_routes = {
    'services.tasks.process_payment': {'queue': 'payments'},
    'consultants.tasks.send_appointment_notification': {'queue': 'notifications'},
}

# Configure task error handling
app.conf.task_annotations = {
    '*': {
        'rate_limit': '10/m',
        'max_retries': 3,
        'default_retry_delay': 300,  # 5 minutes
    }
}

if __name__ == '__main__':
    app.start()

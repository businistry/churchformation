## resources/models.py

from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator

class Resource(models.Model):
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('doc', 'Document'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('image', 'Image'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default='other')
    file_url = models.FileField(
        upload_to='resources/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'mp4', 'mp3', 'jpg', 'png', 'gif'])]
    )
    tags = models.JSONField(default=list)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_resources'
    )

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['file_type']),
            models.Index(fields=['is_premium']),
        ]

class ResourceAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resource_accesses')
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='user_accesses')
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'resource']
        ordering = ['-accessed_at']

    def __str__(self):
        return f"{self.user.email} accessed {self.resource.title}"

class ResourceRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resource_ratings')
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)], default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'resource']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} rated {self.resource.title}: {self.rating}"

class ResourceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Resource Categories"
        ordering = ['name']

class ResourceCategoryAssignment(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='category_assignments')
    category = models.ForeignKey(ResourceCategory, on_delete=models.CASCADE, related_name='resource_assignments')

    class Meta:
        unique_together = ['resource', 'category']

    def __str__(self):
        return f"{self.resource.title} - {self.category.name}"

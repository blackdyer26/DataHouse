import uuid
from django.db import models

class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='datasets/')
    file_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='UPLOADED') 
    # Statuses: UPLOADED, PROFILED, PREPROCESSED, COMPLETED, FAILED

    def __str__(self):
        return self.file_name

class PipelineRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='runs')
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, default='PENDING') 
    # Statuses: PENDING, RUNNING, PAUSED, COMPLETED, FAILED
    current_layer = models.CharField(max_length=100, default='ingestion')
    metrics = models.JSONField(blank=True, null=True) # Will store the AutoGluon leaderboard later
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Run {self.id} - {self.status}"
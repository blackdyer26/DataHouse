from django.db import models
from api.models import PipelineRun

class ChatCommandAudit(models.Model):
    run = models.ForeignKey(PipelineRun, on_delete=models.CASCADE, related_name='chat_commands')
    command_text = models.TextField()
    layer_targeted = models.CharField(max_length=100)
    action_taken = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.layer_targeted} - {self.action_taken}"

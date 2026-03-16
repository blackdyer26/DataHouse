from rest_framework import serializers
from .models import Dataset, PipelineRun

class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = ['id', 'file', 'file_name', 'uploaded_at', 'status']
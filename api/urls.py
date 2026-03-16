from django.urls import path
from .views import DatasetUploadView, PipelineRunDetailView

urlpatterns = [
    path('upload/', DatasetUploadView.as_view(), name='dataset-upload'),
    path('run/<uuid:run_id>/', PipelineRunDetailView.as_view(), name='run-detail'),
]
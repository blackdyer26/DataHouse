import duckdb
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import Dataset, PipelineRun
from .serializers import DatasetSerializer, PipelineRunSerializer
from .tasks import run_autogluon_evaluation

class DatasetUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def detect_problem_type(self, schema):
        """
        Heuristic to guess the target and problem type.
        """
        target_keywords = ['churn', 'target', 'label', 'y', 'output', 'status']
        detected_target = None
        
        for col in schema:
            if col['column'].lower() in target_keywords:
                detected_target = col
                break
        
        if not detected_target:
            detected_target = schema[-1]

        if detected_target['type'] in ['VARCHAR', 'BOOLEAN', 'BIT']:
            return detected_target['column'], 'CLASSIFICATION'
        else:
            return detected_target['column'], 'REGRESSION'

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if 'file' in data and 'file_name' not in data:
            data['file_name'] = data['file'].name

        file_serializer = DatasetSerializer(data=data)
        
        if file_serializer.is_valid():
            dataset = file_serializer.save()
            run = PipelineRun.objects.create(dataset=dataset, status='RUNNING', current_layer='profiling')
            file_path = dataset.file.path
            
            try:
                conn = duckdb.connect(database=':memory:')
                total_rows = conn.execute(f"SELECT COUNT(*) FROM read_csv_auto('{file_path}')").fetchone()[0]
                columns_info = conn.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{file_path}')").fetchall()
                schema = [{"column": col[0], "type": col[1]} for col in columns_info]
                
                target_col, task_type = self.detect_problem_type(schema)
                
                profile_data = {
                    "total_rows": total_rows,
                    "schema": schema,
                    "automated_detection": {
                        "target_column": target_col,
                        "task_category": task_type
                    },
                    "message": f"Detected a {task_type} task targeting '{target_col}'."
                }
                
                run.status = 'PROFILED'
                run.metrics = profile_data
                run.save()

                # Trigger the Background ML Training
                run_autogluon_evaluation.delay(str(run.id), target_col, task_type)

                return Response({
                    "dataset_id": dataset.id,
                    "run_id": run.id,
                    "profile": profile_data,
                    "pipeline_status": "Background ML Training Started"
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                run.status = 'FAILED'
                run.save()
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class PipelineRunDetailView(APIView):
    def get(self, request, run_id, *args, **kwargs):
        try:
            run = PipelineRun.objects.get(id=run_id)
            serializer = PipelineRunSerializer(run)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PipelineRun.DoesNotExist:
            return Response({"error": "Pipeline Run not found."}, status=status.HTTP_404_NOT_FOUND)
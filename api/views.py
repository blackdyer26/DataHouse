from django.shortcuts import render
import duckdb
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import Dataset, PipelineRun
from .serializers import DatasetSerializer

class DatasetUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        # We manually inject the file name if it's not provided in the form data
        data = request.data.copy()
        if 'file' in data and 'file_name' not in data:
            data['file_name'] = data['file'].name

        file_serializer = DatasetSerializer(data=data)
        
        if file_serializer.is_valid():
            # 1. Save the file and log the Dataset
            dataset = file_serializer.save()
            
            # 2. Create the Pipeline Run
            run = PipelineRun.objects.create(dataset=dataset, status='RUNNING', current_layer='profiling')
            
            # 3. DuckDB Rapid Profiling
            file_path = dataset.file.path
            
            try:
                # Connect to in-memory DuckDB and read the CSV
                conn = duckdb.connect(database=':memory:')
                
                # Get total rows
                total_rows = conn.execute(f"SELECT COUNT(*) FROM read_csv_auto('{file_path}')").fetchone()[0]
                
                # Get schema (column names and types)
                columns_info = conn.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{file_path}')").fetchall()
                schema = [{"column": col[0], "type": col[1]} for col in columns_info]
                
                profile_data = {
                    "total_rows": total_rows,
                    "schema": schema,
                    "message": "Dataset profiled successfully by DuckDB."
                }
                
                # 4. Update Run status with metrics
                run.status = 'PROFILED'
                run.metrics = profile_data
                run.save()

                return Response({
                    "dataset_id": dataset.id,
                    "run_id": run.id,
                    "profile": profile_data
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                run.status = 'FAILED'
                run.save()
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

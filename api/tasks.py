from celery import shared_task
from .models import PipelineRun
import pandas as pd
from autogluon.tabular import TabularPredictor
import math
import os

@shared_task
def clean_and_preprocess_data(run_id, target_column, problem_type):
    """
    Automated Data Cleaning Layer: Handles missing values and duplicates.
    """
    try:
        run = PipelineRun.objects.get(id=run_id)
        run.status = 'PREPROCESSING'
        run.current_layer = 'data_cleaning'
        run.save()

        file_path = run.dataset.file.path
        df = pd.read_csv(file_path)

        # --- AUTOMATED CLEANING LOGIC ---
        initial_rows = len(df)
        
        # 1. Drop exact duplicate rows
        df = df.drop_duplicates()
        
        # 2. Impute missing values (Simple strategy)
        for col in df.columns:
            if df[col].isnull().sum() > 0:
                if df[col].dtype in ['int64', 'float64']:
                    df[col] = df[col].fillna(df[col].median()) # Fill numbers with median
                else:
                    df[col] = df[col].fillna('Unknown') # Fill text with 'Unknown'

        rows_removed = initial_rows - len(df)

        # 3. Save the cleaned dataset
        clean_file_path = file_path.replace('.csv', '_cleaned.csv')
        df.to_csv(clean_file_path, index=False)

        # 4. Log the cleaning metrics
        cleaning_metrics = {
            "rows_removed": rows_removed,
            "missing_values_imputed": True,
            "clean_file_path": clean_file_path
        }
        
        if run.metrics is None:
            run.metrics = {}
        run.metrics['cleaning_report'] = cleaning_metrics
        run.save()

        # 5. Chain the next step: Trigger ML Evaluation on the CLEAN data
        run_autogluon_evaluation.delay(run_id, target_column, problem_type, clean_file_path)

        return f"Preprocessing complete. Removed {rows_removed} duplicate rows. Handing off to ML Engine."

    except Exception as e:
        run.status = 'FAILED'
        run.save()
        return f"Error during preprocessing: {str(e)}"

@shared_task
def run_autogluon_evaluation(run_id, target_column, problem_type, data_path=None):
    """
    ML Evaluation Layer. Now accepts a custom data_path (the cleaned data).
    """
    try:
        run = PipelineRun.objects.get(id=run_id)
        run.status = 'TRAINING'
        run.current_layer = 'model_evaluation'
        run.save()

        # Use the cleaned data if provided, otherwise fallback to raw
        file_to_train = data_path if data_path else run.dataset.file.path
        df = pd.read_csv(file_to_train)

        save_path = f'ag_models/run_{run_id}'
        
        predictor = TabularPredictor(
            label=target_column, 
            path=save_path
        ).fit(df, time_limit=60, presets='good_quality')

        leaderboard_df = predictor.leaderboard(silent=True)
        leaderboard_records = leaderboard_df.to_dict(orient='records')
        
        clean_leaderboard = []
        for record in leaderboard_records:
            clean_record = {}
            for k, v in record.items():
                if isinstance(v, float) and math.isnan(v):
                    clean_record[k] = None
                else:
                    clean_record[k] = v
            clean_leaderboard.append(clean_record)

        run.metrics['leaderboard'] = clean_leaderboard
        run.metrics['best_model'] = predictor.model_best
        run.status = 'COMPLETED'
        run.save()

        return f"Training completed on {len(df)} rows. Best model: {predictor.model_best}"

    except Exception as e:
        run.status = 'FAILED'
        run.save()
        return f"Error during training: {str(e)}"
from celery import shared_task
from .models import PipelineRun
import pandas as pd
from autogluon.tabular import TabularPredictor
import math

@shared_task
def run_autogluon_evaluation(run_id, target_column, problem_type):
    try:
        run = PipelineRun.objects.get(id=run_id)
        run.status = 'TRAINING'
        run.current_layer = 'model_evaluation'
        run.save()

        file_path = run.dataset.file.path
        df = pd.read_csv(file_path)

        save_path = f'ag_models/run_{run_id}'
        
        predictor = TabularPredictor(
            label=target_column, 
            path=save_path
        ).fit(
            df, 
            time_limit=60, 
            presets='good_quality' 
        )

        # 1. Get the leaderboard
        leaderboard_df = predictor.leaderboard(silent=True)
        
        # 2. Convert to dictionary records
        leaderboard_records = leaderboard_df.to_dict(orient='records')
        
        # 3. SCRUB NaN VALUES: Standard JSON doesn't accept 'NaN'. We replace them with None (which becomes 'null' in JSON)
        clean_leaderboard = []
        for record in leaderboard_records:
            clean_record = {}
            for k, v in record.items():
                if isinstance(v, float) and math.isnan(v):
                    clean_record[k] = None
                else:
                    clean_record[k] = v
            clean_leaderboard.append(clean_record)

        # 4. Save clean data and use the modern .model_best attribute
        run.metrics['leaderboard'] = clean_leaderboard
        run.metrics['best_model'] = predictor.model_best
        run.status = 'COMPLETED'
        run.save()

        return f"Training completed. Best model: {predictor.model_best}"

    except Exception as e:
        run.status = 'FAILED'
        run.save()
        return f"Error during training: {str(e)}"
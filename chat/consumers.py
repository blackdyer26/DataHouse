import json
import re
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from api.models import PipelineRun
from .models import ChatCommandAudit

class ChatMiddlewareConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({
            'message': 'DataHouse Middleware Online. How can I help with your pipeline?'
        }))

    async def receive(self, text_data):
        data = json.loads(text_data)
        user_msg = data.get('message', '')
        run_id = data.get('run_id')

        # Regex to catch @layer_name commands
        # Example: "@problem_detector change target to age"
        match = re.search(r"@(\w+)\s+(.*)", user_msg)
        
        if match:
            layer = match.group(1)
            instruction = match.group(2)
            
            # Process the override
            response_msg = await self.handle_layer_override(run_id, layer, instruction)
        else:
            response_msg = "I'm listening. Use @layer_name to override automated steps."

        await self.send(text_data=json.dumps({
            'message': response_msg
        }))

    @database_sync_to_async
    def handle_layer_override(self, run_id, layer, instruction):
        try:
            run = PipelineRun.objects.get(id=run_id)
            
            # Log the audit trail
            ChatCommandAudit.objects.create(
                run=run,
                command_text=instruction,
                layer_targeted=layer,
                action_taken="OVERRIDE_RECEIVED"
            )

            # Logic for specific layers
            if layer == "problem_detector":
                # In a full app, you'd parse 'instruction' to extract the new target
                # For this sprint, we acknowledge and log the intent
                run.status = "PAUSED" # Pause to wait for human tuning
                run.save()
                return f"Layer '{layer}' intercepted. Intent: '{instruction}'. Pipeline paused for manual tuning."
            
            return f"Command received for @{layer}. Processing..."
        except Exception as e:
            return f"Error connecting to run: {str(e)}"
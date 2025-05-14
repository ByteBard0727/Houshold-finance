from channels.generic.websocket import AsyncWebsocketConsumer
import json

class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handle the WebSocket connection."""
        self.group_name = "dashboard_group"
        
        # Join the WebSocket group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave the group when the WebSocket is closed
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def send_dashboard_data(self, event):
        print("Data sent to WebSocket:", event['data'])  # Check if the correct data is being sent
        await self.send(text_data=json.dumps(event['data']))
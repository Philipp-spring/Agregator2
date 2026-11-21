import httpx


class CapashinoClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def send_notification(self, message: str, reference_id: str, idempotency_key: str):
        payload = {
                "message": message, 
                "reference_id": reference_id, 
                "idempotency_key": idempotency_key,
                }
        
        response  = await self.client.post("/api/notifications", json=payload)
        response.raise_for_status()
        return response.json()

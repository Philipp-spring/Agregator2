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
        
        response = await self.client.post("/api/notifications", json=payload)

        if response.status_code >= 400:
            # Выводим тело ошибки в лог, чтобы понять причину
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Capashino error %s: %s", response.status_code, response.text)

        response.raise_for_status()
        return response.json()

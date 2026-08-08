import httpx

from app.config import settings


class PrometheusScraper:
    def __init__(self):
        self.base_url = settings.PROMETHEUS_URL
        
    async def query(self, query_str: str):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/query", params={"query": query_str}
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def get_pod_metrics(self, namespace: str, pod_name: str):
        query = (
            'sum(rate(container_cpu_usage_seconds_total{namespace='
            f'"{namespace}", pod="{pod_name}"}}[5m]))'
        )
        return await self.query(query)
        
prometheus_scraper = PrometheusScraper()

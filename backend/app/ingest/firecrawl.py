"""firecrawl client, for live url-to-markdown. one of two optional external
services in beholder (tavily is the other), and always swappable: the client
is transport-injectable, tests never touch the network. pdf and docx uploads
never reach this file: they parse locally, see ingest.docs."""

import httpx

from ..config import settings


class FirecrawlClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self.api_key = api_key or settings.firecrawl_api_key
        self.base_url = base_url or settings.firecrawl_base_url
        self.transport = transport  # tests inject a mock transport; prod never does

    def _require_key(self) -> str:
        if not self.api_key:
            raise RuntimeError("firecrawl is not configured: set BEHOLDER_FIRECRAWL_KEY")
        return self.api_key

    async def scrape_markdown(self, url: str) -> str:
        """url in, markdown out. for live pages a local parser cannot read."""
        key = self._require_key()
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            r = await client.post(
                f"{self.base_url}/v1/scrape",
                json={"url": url, "formats": ["markdown"]},
                headers={"authorization": f"bearer {key}"},
            )
            r.raise_for_status()
            data = r.json()
        return data.get("data", {}).get("markdown", "")

"""beholder settings. everything comes from the environment, never from the repo."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # any postgres url. sqlite works for dev and tests.
    database_url: str = "sqlite+aiosqlite:///./beholder.db"

    # the api verifies jwts issued by supabase auth (standard jwks). a self-host
    # swaps this url and nothing else; supabase is hosted postgres with standard
    # protocols, so nothing here is supabase-only.
    supabase_url: str | None = None
    supabase_audience: str = "authenticated"

    # the model gateway. glm through an openai-compatible endpoint.
    glm_api_key: str | None = None
    glm_base_url: str = "https://api.z.ai/api/paas/v4"
    glm_model: str = "glm-4.6"

    # provider for the gateway: "glm", or "mock"/"demo" for local runs
    # without keys (canned outputs that exercise the whole flow)
    gateway_provider: str = "glm"

    # forge urls: gitlab and gitea are usually self-hosted, github and
    # bitbucket cloud are fixed. urls and tokens stay overridable, always.
    github_token: str | None = None
    gitlab_url: str = "https://gitlab.com/api/v4"
    gitlab_token: str | None = None
    bitbucket_token: str | None = None
    gitea_url: str = "https://gitea.com/api/v1"
    gitea_token: str | None = None

    # firecrawl: pdf, docx, and url to markdown. optional: direct formats
    # (md, txt, json) never need it, and the doc-site crawler is plain http.
    firecrawl_api_key: str | None = None
    firecrawl_base_url: str = "https://api.firecrawl.dev"

    # dev only: skip jwt verification. never enable with a public bind.
    dev_auth: bool = False

    # run the job worker inside the api process. one queue, one worker type.
    inline_worker: bool = True

    model_config = {"env_prefix": "BEHOLDER_", "env_file": ".env"}


settings = Settings()

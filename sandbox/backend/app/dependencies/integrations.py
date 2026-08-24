# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from typing import Annotated

import httpx2
from fastapi import Depends, Request


# ============================================================
# Functions
# ============================================================

def get_integration_http_client(request: Request) -> httpx2.AsyncClient:
    """Inject the shared outbound HTTP client created in the app lifespan."""
    return request.app.state.integration_http_client


# ============================================================
# Dependencies
# ============================================================

IntegrationHttpClientDep = Annotated[httpx2.AsyncClient, Depends(get_integration_http_client)]

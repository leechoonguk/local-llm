# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.dependencies.core import SessionDep
from app.services.batch import BatchService
from app.services.integration.operation import IntegrationOperationService
from app.services.integration.provider import IntegrationProviderService
from app.services.integration.secret import IntegrationSecretService
from app.services.refresh import RefreshService
from app.services.user import UserService


# ============================================================
# Functions
# ============================================================

def get_batch_service(session: SessionDep) -> BatchService:
    return BatchService(session)


def get_integration_provider_service(session: SessionDep) -> IntegrationProviderService:
    return IntegrationProviderService(session)


def get_integration_secret_service(session: SessionDep) -> IntegrationSecretService:
    return IntegrationSecretService(session)


def get_integration_operation_service(session: SessionDep) -> IntegrationOperationService:
    return IntegrationOperationService(session)


def get_refresh_service(session: SessionDep) -> RefreshService:
    return RefreshService(session)


def get_user_service(session: SessionDep) -> UserService:
    return UserService(session)


# ============================================================
# Dependencies
# ============================================================

BatchServiceDep = Annotated[BatchService, Depends(get_batch_service)]
IntegrationProviderServiceDep = Annotated[
    IntegrationProviderService, Depends(get_integration_provider_service)
]
IntegrationSecretServiceDep = Annotated[
    IntegrationSecretService, Depends(get_integration_secret_service)
]
IntegrationOperationServiceDep = Annotated[
    IntegrationOperationService, Depends(get_integration_operation_service)
]
RefreshServiceDep = Annotated[RefreshService, Depends(get_refresh_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]

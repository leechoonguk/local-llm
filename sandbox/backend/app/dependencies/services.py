# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.dependencies.core import SessionDep
from app.services.batch.run import BatchRunService
from app.services.batch.schedule import BatchScheduleService
from app.services.batch.step import BatchStepService
from app.services.integration.operation import IntegrationOperationService
from app.services.integration.provider import IntegrationProviderService
from app.services.integration.secret import IntegrationSecretService
from app.services.refresh import RefreshService
from app.services.user import UserService


# ============================================================
# Functions
# ============================================================


def get_batch_step_service(session: SessionDep) -> BatchStepService:
    return BatchStepService(session)


def get_batch_run_service(session: SessionDep) -> BatchRunService:
    return BatchRunService(session)


def get_batch_schedule_service(session: SessionDep) -> BatchScheduleService:
    return BatchScheduleService(session)


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

BatchRunServiceDep = Annotated[BatchRunService, Depends(get_batch_run_service)]
BatchScheduleServiceDep = Annotated[BatchScheduleService, Depends(get_batch_schedule_service)]
BatchStepServiceDep = Annotated[BatchStepService, Depends(get_batch_step_service)]
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

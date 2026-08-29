# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.dependencies.core import SessionDep
from app.services.batch import BatchService
from app.services.integration import IntegrationService
from app.services.notice import NoticeService
from app.services.user import UserService


# ============================================================
# Functions
# ============================================================

def get_batch_service(session: SessionDep) -> BatchService:
    return BatchService(session)


def get_integration_service(session: SessionDep) -> IntegrationService:
    return IntegrationService(session)


def get_notice_service(session: SessionDep) -> NoticeService:
    return NoticeService(session)


def get_user_service(session: SessionDep) -> UserService:
    return UserService(session)


# ============================================================
# Dependencies
# ============================================================

BatchServiceDep = Annotated[BatchService, Depends(get_batch_service)]
IntegrationServiceDep = Annotated[IntegrationService, Depends(get_integration_service)]
NoticeServiceDep = Annotated[NoticeService, Depends(get_notice_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]

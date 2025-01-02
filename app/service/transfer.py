from datetime import datetime, timedelta
from copy import deepcopy
from imghdr import test_rast
from uuid import uuid4

from fastapi import status

from app.core.error import ErrorCode
from app.core.response import APIError
from app.entity import (
    User as UserEntity,
    Domain as DomainEntity,
    TransferInvite as TransferInviteEntity,
)


class DomainTransferService:

    @staticmethod
    async def create_transfer_link(
        user: UserEntity,
        domain: DomainEntity,
        transfer_user_email: str,
    ) -> TransferInviteEntity:
        one_week_later = datetime.now() + timedelta(days=7)
        transfer_invite = await TransferInviteEntity.create(
            id=uuid4(),
            name=domain.name,
            domain=domain,
            user=user,
            transfer_user_email=transfer_user_email,
            expired_at=one_week_later,
        )
        return transfer_invite

    @staticmethod
    async def get_transfer_invite(
        transfer_invite_id: str,
    ) -> TransferInviteEntity:
        invite_entity = await TransferInviteEntity.get_or_none(id=transfer_invite_id)
        if not invite_entity:
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.INVALID_INVITE,
                message="존재하지 않는 초대입니다.",
            )
        return invite_entity

    @staticmethod
    async def accept_transfer_invite(
        transfer_invite: TransferInviteEntity, target_user: UserEntity
    ) -> DomainEntity:
        if transfer_invite.expired_at.replace(tzinfo=None) < datetime.now():
            await transfer_invite.delete()
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.EXPIRED_INVITE,
                message="만료된 초대입니다.",
            )
        if transfer_invite.transfer_user_email != target_user.email:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_INVITE,
                message="유효하지 않은 초대입니다.",
            )
        await transfer_invite.fetch_related("domain")
        new_domain_entity = await DomainEntity.create(
            name=transfer_invite.name,
            record_id=transfer_invite.domain.record_id,
        )
        await target_user.domains.add(new_domain_entity)
        await transfer_invite.delete()
        await transfer_invite.domain.delete()
        return new_domain_entity

    @staticmethod
    async def reject_transfer_invite(
        transfer_invite: TransferInviteEntity, target_user: UserEntity
    ) -> None:
        if transfer_invite.transfer_user_email != target_user.email:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code=ErrorCode.INVALID_INVITE,
                message="유효하지 않은 초대입니다.",
            )
        await transfer_invite.delete()

from enum import IntEnum
from typing import Any

from pydantic import BaseModel


class InteractionType(IntEnum):
    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3


class InteractionCallbackType(IntEnum):
    # 서버의 핑 요청에 대한 응답
    PONG = 1

    # 메시지와 함께 채널에 응답
    CHANNEL_MESSAGE = 4

    # 메시지를 지연시키고 나중에 응답
    DEFERRED_CHANNEL_MESSAGE = 5

    # 메시지를 지연시키고 나중에 응답 (응답은 사용자에게만 표시)
    DEFERRED_MESSAGE_UPDATE = 6

    # 원본 메시지 업데이트
    UPDATE_MESSAGE = 7

    # 자동완성 선택지 제공
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8

    # 모달 표시
    MODAL = 9

    # 프리미엄(고급) 응답
    PREMIUM_REQUIRED = 10


class MessageFlags(IntEnum):

    # 임시 응답 (사용자에게만 표시)
    EPHEMERAL = 1 << 6

    # 메시지 내용 로드 억제
    SUPPRESS_EMBEDS = 1 << 2

    # 긴급 메시지
    URGENT = 1 << 13


class ComponentType(IntEnum):
    # 컴포넌트 그룹
    ACTION_ROW = 1

    # 버튼
    BUTTON = 2

    # 문자열 선택 메뉴
    STRING_SELECT = 3

    # 텍스트 입력
    TEXT_INPUT = 4

    # 사용자 선택 메뉴
    USER_SELECT = 5

    # 역할 선택 메뉴
    ROLE_SELECT = 6

    # 멘션 가능 선택 메뉴
    MENTIONABLE_SELECT = 7

    # 채널 선택 메뉴
    CHANNEL_SELECT = 8


class ButtonStyle(IntEnum):
    # 기본 스타일
    PRIMARY = 1

    # 회색 배경
    SECONDARY = 2

    # 초록색 배경
    SUCCESS = 3

    # 빨간색 배경
    DANGER = 4

    # 링크 스타일
    LINK = 5


def create_interaction_response(content: str, ephemeral: bool = False):
    response = {
        "type": InteractionCallbackType.CHANNEL_MESSAGE,
        "data": {"content": content},
    }

    if ephemeral:
        response["data"]["flags"] = MessageFlags.EPHEMERAL

    return response


def create_modal(custom_id: str, title: str):
    return {
        "type": InteractionCallbackType.MODAL,
        "data": {"custom_id": custom_id, "title": title, "components": []},
    }


class InteractionResponse(BaseModel):
    type: InteractionCallbackType
    data: dict[str, Any]

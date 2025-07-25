#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""The crud package, containing essential business logic, services, and routing configurations for the playground ops."""

from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select

from budapp.commons import logging
from budapp.commons.db_utils import DataManagerUtils

from .models import ChatSession, ChatSetting, Message, Note


logger = logging.get_logger(__name__)


class ChatSessionDataManager(DataManagerUtils):
    """Data manager for the ChatSession model."""

    async def get_all_chat_sessions(
        self,
        user_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[ChatSession], int]:
        """List all workflows from the database."""
        await self.validate_fields(ChatSession, filters)

        # Generate base query for chat sessions
        base_stmt = (
            select(ChatSession, func.coalesce(func.sum(Message.total_tokens), 0).label("total_tokens"))
            .join(Message, ChatSession.id == Message.chat_session_id, isouter=True)
            .where(ChatSession.user_id == user_id)
            .group_by(ChatSession.id)
        )

        # Apply filters
        if search:
            search_conditions = await self.generate_search_stmt(ChatSession, filters)
            stmt = base_stmt.filter(or_(*search_conditions))
            count_stmt = (
                select(func.count())
                .select_from(ChatSession)
                .where(ChatSession.user_id == user_id)
                .filter(or_(*search_conditions))
            )
        else:
            stmt = base_stmt.filter_by(**filters)
            count_stmt = (
                select(func.count())
                .select_from(ChatSession)
                .where(ChatSession.user_id == user_id)
                .filter_by(**filters)
            )

        # Count query
        count = self.execute_scalar(count_stmt)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(ChatSession, order_by)
            stmt = stmt.order_by(*sort_conditions)

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        result = self.session.execute(stmt)

        return result, count


class MessageDataManager(DataManagerUtils):
    """Data manager for the Messaage model."""

    async def get_last_message(self, chat_session_id: UUID) -> Message | None:
        """Fetch the last inserted message for a given chat session."""
        return self.scalar_one_or_none(
            select(Message)
            .where(Message.chat_session_id == chat_session_id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )

    async def get_messages(
        self,
        chat_session_id: UUID,
        filters: Dict,
        offset: int,
        limit: int,
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Message], int]:
        """Fetch chat messages for a given chat session, ordered by created_at."""
        await self.validate_fields(Message, {"chat_session_id": chat_session_id})
        await self.validate_fields(Message, filters)

        # Generate base query
        base_stmt = select(Message).where(Message.chat_session_id == chat_session_id)

        # Apply filters
        if search:
            search_conditions = await self.generate_search_stmt(Message, filters)
            stmt = base_stmt.filter(or_(*search_conditions))
            count_stmt = select(func.count()).select_from(Message).filter(or_(*search_conditions))
        else:
            stmt = base_stmt.filter_by(**filters)
            count_stmt = select(func.count()).select_from(Message).filter_by(**filters)

        # Count messages before pagination
        count = self.execute_scalar(count_stmt)

        # Apply ordering
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Message, order_by)
            stmt = stmt.order_by(*sort_conditions)

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        # Execute query
        result = self.scalars_all(stmt)

        return result, count


class ChatSettingDataManager(DataManagerUtils):
    """Data manager for the ChatSetting model."""

    async def get_all_chat_settings(
        self,
        user_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[ChatSetting], int]:
        """List all chat settings from the database."""
        await self.validate_fields(ChatSetting, filters)

        # Generate base query for chat settings
        base_stmt = select(ChatSetting).where(ChatSetting.user_id == user_id)

        # Apply filters
        if search:
            search_conditions = await self.generate_search_stmt(ChatSetting, filters)
            stmt = base_stmt.filter(or_(*search_conditions))
            count_stmt = (
                select(func.count())
                .select_from(ChatSetting)
                .where(ChatSetting.user_id == user_id)
                .filter(or_(*search_conditions))
            )
        else:
            stmt = base_stmt.filter_by(**filters)
            count_stmt = (
                select(func.count())
                .select_from(ChatSetting)
                .where(ChatSetting.user_id == user_id)
                .filter_by(**filters)
            )

        # Count query
        count = self.execute_scalar(count_stmt)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(ChatSetting, order_by)
            stmt = stmt.order_by(*sort_conditions)

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        result = self.scalars_all(stmt)

        return result, count


class NoteDataManager(DataManagerUtils):
    """Data manager for the Note model."""

    async def get_all_notes(
        self,
        chat_session_id: UUID,
        user_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Note], int]:
        """Retrieve all notes from the database for a given chat session and user."""
        await self.validate_fields(Note, filters)

        # Generate base query for notes
        base_stmt = select(Note).where(Note.chat_session_id == chat_session_id, Note.user_id == user_id)

        # Apply filters
        if search:
            search_conditions = await self.generate_search_stmt(Note, filters)
            stmt = base_stmt.filter(or_(*search_conditions))
            count_stmt = (
                select(func.count())
                .select_from(Note)
                .where(Note.chat_session_id == chat_session_id, Note.user_id == user_id)
                .filter(or_(*search_conditions))
            )
        else:
            stmt = base_stmt.filter_by(**filters)
            count_stmt = (
                select(func.count())
                .select_from(Note)
                .where(Note.chat_session_id == chat_session_id, Note.user_id == user_id)
                .filter_by(**filters)
            )

        # Count query
        count = self.execute_scalar(count_stmt)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Note, order_by)
            stmt = stmt.order_by(*sort_conditions)

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        result = self.scalars_all(stmt)

        return result, count

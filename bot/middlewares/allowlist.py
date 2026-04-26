import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)

class AllowlistMiddleware(BaseMiddleware):
    def __init__(self, allowed_id: int):
        self.allowed_id = allowed_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Get the user ID from the event (e.g., Message)
        user = data.get("event_from_user")
        
        if not user:
            return await handler(event, data)
        
        if user.id != self.allowed_id:
            logger.warning(f"Unauthorized access attempt from user {user.id}")
            # If it's a message, we can optionally reply, or just ignore. 
            # The spec says "бот игнорирует сообщение", so we return nothing.
            return
            
        return await handler(event, data)

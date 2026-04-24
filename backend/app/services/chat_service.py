import os
import logging
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiofiles
import time

from models.schemas import ChatInfo, MessageInfo
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self):
        self.chat_dir = os.path.join(os.getenv("UPLOAD_DIR", "./data/uploads"), "chats")
        self.llm_service = LLMService()

        # Ensure chat directory exists
        os.makedirs(self.chat_dir, exist_ok=True)

    async def initialize(self):
        """Initialize chat service"""
        try:
            await self.llm_service.initialize()
            logger.info("Chat service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize chat service: {e}")
            raise

    async def create_chat(self, title: str, document_id: str) -> Dict[str, Any]:
        """Create a new chat session"""
        try:
            # Generate chat ID
            chat_id = self._generate_chat_id(title, document_id)

            # Create chat info
            chat_info = {
                "id": chat_id,
                "title": title,
                "document_id": document_id,
                "message_count": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "last_message_preview": None,
            }

            # Save chat info
            await self._save_chat_info(chat_id, chat_info)

            # Create messages file
            await self._save_messages(chat_id, [])

            logger.info(f"Created new chat: {chat_id}")
            return chat_info

        except Exception as e:
            logger.error(f"Failed to create chat: {e}")
            raise

    async def send_message(
        self,
        message: str,
        document_id: str,
        chat_id: Optional[str],
        vector_service,
        embedding_service,
        context_length: int = 5,
    ) -> Dict[str, Any]:
        """Send message and get AI response"""
        try:
            start_time = time.time()

            # If no chat_id provided, create a new chat
            if not chat_id:
                # Generate title from first few words of message
                title = self._generate_chat_title(message)
                chat_info = await self.create_chat(title, document_id)
                chat_id = chat_info["id"]

            # Get query embedding
            query_embedding = await embedding_service.encode_text(message)
            if not query_embedding:
                raise ValueError("Failed to generate query embedding")

            # Search for relevant chunks
            search_results, similarities = await vector_service.search_similar(
                query_embedding=query_embedding,
                document_id=document_id,
                n_results=context_length,
                similarity_threshold=0.3,
            )

            # Generate AI response
            response_data = await self.llm_service.generate_response(
                query=message, context_chunks=search_results
            )

            # Save user message
            user_message = {
                "id": self._generate_message_id(),
                "chat_id": chat_id,
                "content": message,
                "is_user": True,
                "sources": [],
                "confidence_score": None,
                "created_at": datetime.now().isoformat(),
            }

            # Save AI response
            ai_message = {
                "id": self._generate_message_id(),
                "chat_id": chat_id,
                "content": response_data["response"],
                "is_user": False,
                "sources": response_data.get("sources", []),
                "confidence_score": self._calculate_confidence_score(similarities),
                "created_at": datetime.now().isoformat(),
            }

            # Load existing messages and add new ones
            messages = await self._load_messages(chat_id)
            messages.extend([user_message, ai_message])

            # Save updated messages
            await self._save_messages(chat_id, messages)

            # Update chat info
            await self._update_chat_info(
                chat_id,
                {
                    "message_count": len(messages),
                    "updated_at": datetime.now().isoformat(),
                    "last_message_preview": message[:100]
                    + ("..." if len(message) > 100 else ""),
                },
            )

            processing_time = time.time() - start_time

            return {
                "response": response_data["response"],
                "sources": response_data.get("sources", []),
                "confidence_score": ai_message["confidence_score"],
                "processing_time": processing_time,
                "chat_id": chat_id,
                "tokens_used": response_data.get("tokens_used"),
                "model_used": response_data.get("model_used"),
            }

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {
                "response": f"I apologize, but I encountered an error: {str(e)}",
                "sources": [],
                "confidence_score": 0.0,
                "processing_time": 0.0,
                "chat_id": chat_id,
                "error": str(e),
            }

    async def get_chat_messages(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a chat"""
        try:
            messages = await self._load_messages(chat_id)
            return messages
        except Exception as e:
            logger.error(f"Failed to get chat messages: {e}")
            return []

    async def get_all_chats(self) -> List[Dict[str, Any]]:
        """Get all chat sessions"""
        chats = []

        try:
            for filename in os.listdir(self.chat_dir):
                if filename.endswith("_info.json"):
                    chat_id = filename.replace("_info.json", "")

                    try:
                        chat_info = await self._load_chat_info(chat_id)
                        if chat_info:
                            chats.append(chat_info)
                    except Exception as e:
                        logger.warning(f"Failed to load chat info for {chat_id}: {e}")
                        continue

            # Sort by updated date (newest first)
            chats.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        except Exception as e:
            logger.error(f"Failed to get chats: {e}")

        return chats

    async def get_chats_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chats for a specific document"""
        all_chats = await self.get_all_chats()
        return [chat for chat in all_chats if chat.get("document_id") == document_id]

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat and all its messages"""
        try:
            # Delete chat info file
            info_file = os.path.join(self.chat_dir, f"{chat_id}_info.json")
            if os.path.exists(info_file):
                os.unlink(info_file)

            # Delete messages file
            messages_file = os.path.join(self.chat_dir, f"{chat_id}_messages.json")
            if os.path.exists(messages_file):
                os.unlink(messages_file)

            logger.info(f"Chat {chat_id} deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to delete chat {chat_id}: {e}")
            return False

    async def update_chat_title(self, chat_id: str, new_title: str) -> bool:
        """Update chat title"""
        try:
            await self._update_chat_info(
                chat_id, {"title": new_title, "updated_at": datetime.now().isoformat()}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update chat title: {e}")
            return False

    def _generate_chat_id(self, title: str, document_id: str) -> str:
        """Generate unique chat ID"""
        timestamp = datetime.now().isoformat()
        combined = f"{title}_{document_id}_{timestamp}"
        return hashlib.md5(combined.encode()).hexdigest()[:12]

    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]

    def _generate_chat_title(self, message: str) -> str:
        """Generate chat title from first message"""
        # Take first few words, max 50 characters
        words = message.split()[:8]
        title = " ".join(words)
        return title[:50] + ("..." if len(title) > 50 else "")

    def _calculate_confidence_score(self, similarities: List[float]) -> float:
        """Calculate confidence score from similarity scores"""
        if not similarities:
            return 0.0

        # Average of top similarities, weighted by position
        weights = [1.0, 0.8, 0.6, 0.4, 0.2]
        weighted_sum = 0.0
        weight_sum = 0.0

        for i, sim in enumerate(similarities[:5]):
            weight = weights[i] if i < len(weights) else 0.1
            weighted_sum += sim * weight
            weight_sum += weight

        return weighted_sum / weight_sum if weight_sum > 0 else 0.0

    async def _save_chat_info(self, chat_id: str, chat_info: Dict[str, Any]):
        """Save chat information to file"""
        info_file = os.path.join(self.chat_dir, f"{chat_id}_info.json")

        async with aiofiles.open(info_file, "w") as f:
            await f.write(json.dumps(chat_info, indent=2))

    async def _load_chat_info(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Load chat information from file"""
        info_file = os.path.join(self.chat_dir, f"{chat_id}_info.json")

        if not os.path.exists(info_file):
            return None

        try:
            async with aiofiles.open(info_file, "r") as f:
                return json.loads(await f.read())
        except Exception as e:
            logger.error(f"Failed to load chat info {chat_id}: {e}")
            return None

    async def _update_chat_info(self, chat_id: str, updates: Dict[str, Any]):
        """Update chat information"""
        chat_info = await self._load_chat_info(chat_id)
        if chat_info:
            chat_info.update(updates)
            await self._save_chat_info(chat_id, chat_info)

    async def _save_messages(self, chat_id: str, messages: List[Dict[str, Any]]):
        """Save messages to file"""
        messages_file = os.path.join(self.chat_dir, f"{chat_id}_messages.json")

        async with aiofiles.open(messages_file, "w") as f:
            await f.write(json.dumps(messages, indent=2))

    async def _load_messages(self, chat_id: str) -> List[Dict[str, Any]]:
        """Load messages from file"""
        messages_file = os.path.join(self.chat_dir, f"{chat_id}_messages.json")

        if not os.path.exists(messages_file):
            return []

        try:
            async with aiofiles.open(messages_file, "r") as f:
                return json.loads(await f.read())
        except Exception as e:
            logger.error(f"Failed to load messages for {chat_id}: {e}")
            return []

    async def get_chat_stats(self) -> Dict[str, Any]:
        """Get chat statistics"""
        try:
            all_chats = await self.get_all_chats()
            total_messages = sum(chat.get("message_count", 0) for chat in all_chats)

            return {
                "total_chats": len(all_chats),
                "total_messages": total_messages,
                "avg_messages_per_chat": (
                    total_messages / len(all_chats) if all_chats else 0
                ),
            }
        except Exception as e:
            logger.error(f"Failed to get chat stats: {e}")
            return {"total_chats": 0, "total_messages": 0, "avg_messages_per_chat": 0}

    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.llm_service.cleanup()
            logger.info("Chat service cleaned up")
        except Exception as e:
            logger.error(f"Error during chat service cleanup: {e}")

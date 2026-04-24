import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import JSONResponse

from models.schemas import (
    ChatRequest, ChatResponse, CreateChatRequest, 
    SearchRequest, SearchResponse, ChatStatsResponse
)
from services.chat_service import ChatService
from services.document_service import DocumentService

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
chat_service = ChatService()
document_service = DocumentService()

def get_services(request: Request):
    """Dependency to get services from app state"""
    return {
        "vector_service": request.app.state.vector_service,
        "embedding_service": request.app.state.embedding_service
    }

@router.post("/chat", response_model=ChatResponse)
async def chat_with_document(
    request: ChatRequest,
    services: dict = Depends(get_services)
):
    """Send a message and get AI response"""
    try:
        # Validate document exists
        document = await document_service.get_document_by_id(request.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Initialize chat service if needed
        if not hasattr(chat_service, 'llm_service') or not chat_service.llm_service.client:
            await chat_service.initialize()
        
        # Send message and get response
        response = await chat_service.send_message(
            message=request.message,
            document_id=request.document_id,
            chat_id=request.chat_id,
            vector_service=services["vector_service"],
            embedding_service=services["embedding_service"],
            context_length=request.context_length or 5
        )
        
        return ChatResponse(
            response=response["response"],
            sources=response.get("sources", []),
            confidence_score=response.get("confidence_score"),
            processing_time=response.get("processing_time"),
            tokens_used=response.get("tokens_used")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@router.post("/chats")
async def create_chat(request: CreateChatRequest):
    """Create a new chat session"""
    try:
        # Validate document exists
        document = await document_service.get_document_by_id(request.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Initialize chat service if needed
        if not hasattr(chat_service, 'llm_service') or not chat_service.llm_service.client:
            await chat_service.initialize()
        
        # Create chat
        chat = await chat_service.create_chat(
            title=request.title,
            document_id=request.document_id
        )
        
        return chat
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create chat: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chat session")

@router.get("/chats")
async def get_chats(document_id: Optional[str] = Query(None)):
    """Get all chat sessions, optionally filtered by document"""
    try:
        if document_id:
            # Get chats for specific document
            chats = await chat_service.get_chats_by_document(document_id)
        else:
            # Get all chats
            chats = await chat_service.get_all_chats()
        
        # Format response
        formatted_chats = []
        for chat in chats:
            formatted_chat = {
                "id": chat["id"],
                "title": chat["title"],
                "timestamp": chat["updated_at"][:19].replace('T', ' '),
                "preview": chat.get("last_message_preview", "New chat"),
                "document_id": chat["document_id"],
                "message_count": chat.get("message_count", 0)
            }
            formatted_chats.append(formatted_chat)
        
        return formatted_chats
        
    except Exception as e:
        logger.error(f"Failed to get chats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chats")

@router.get("/chats/{chat_id}")
async def get_chat(chat_id: str):
    """Get a specific chat session"""
    try:
        chat_info = await chat_service._load_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return chat_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat")

@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: str):
    """Get all messages for a chat session"""
    try:
        messages = await chat_service.get_chat_messages(chat_id)
        
        # Format messages for frontend
        formatted_messages = []
        for msg in messages:
            formatted_msg = {
                "id": msg["id"],
                "type": "user" if msg["is_user"] else "ai",
                "content": msg["content"],
                "timestamp": msg["created_at"][:19].replace('T', ' '),
                "sources": msg.get("sources", []),
                "confidence_score": msg.get("confidence_score")
            }
            formatted_messages.append(formatted_msg)
        
        return formatted_messages
        
    except Exception as e:
        logger.error(f"Failed to get messages for chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat messages")

@router.put("/chats/{chat_id}/title")
async def update_chat_title(chat_id: str, title: str):
    """Update chat title"""
    try:
        success = await chat_service.update_chat_title(chat_id, title)
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return {"message": "Chat title updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update chat title: {e}")
        raise HTTPException(status_code=500, detail="Failed to update chat title")

@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a chat session and all its messages"""
    try:
        success = await chat_service.delete_chat(chat_id)
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        return {"message": "Chat deleted successfully", "chat_id": chat_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chat")

@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    services: dict = Depends(get_services)
):
    """Search across documents or within a specific document"""
    try:
        import time
        start_time = time.time()
        
        # Generate query embedding
        embedding_service = services["embedding_service"]
        query_embedding = await embedding_service.encode_text(request.query)
        
        if not query_embedding:
            raise HTTPException(status_code=500, detail="Failed to generate query embedding")
        
        # Search in vector database
        vector_service = services["vector_service"]
        
        if request.document_id:
            # Search within specific document
            results, similarities = await vector_service.search_similar(
                query_embedding=query_embedding,
                document_id=request.document_id,
                n_results=request.limit or 10,
                similarity_threshold=request.similarity_threshold or 0.5
            )
        else:
            # Search across all documents
            results = await vector_service.search_across_documents(
                query_embedding=query_embedding,
                n_results=request.limit or 10,
                similarity_threshold=request.similarity_threshold or 0.5
            )
        
        # Format results
        search_results = []
        for result in results:
            search_result = {
                "chunk_id": result.get("id", ""),
                "document_id": result.get("metadata", {}).get("document_id", ""),
                "content": result.get("content", ""),
                "similarity_score": result.get("similarity_score", 0.0),
                "metadata": result.get("metadata", {})
            }
            search_results.append(search_result)
        
        processing_time = time.time() - start_time
        
        return SearchResponse(
            results=search_results,
            query=request.query,
            total_results=len(search_results),
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/chat-stats", response_model=ChatStatsResponse)
async def get_chat_stats():
    """Get chat usage statistics"""
    try:
        stats = await chat_service.get_chat_stats()
        
        return ChatStatsResponse(
            total_chats=stats["total_chats"],
            total_messages=stats["total_messages"],
            avg_response_time=stats.get("avg_messages_per_chat")
        )
        
    except Exception as e:
        logger.error(f"Failed to get chat stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat statistics")

@router.post("/chats/{chat_id}/regenerate")
async def regenerate_last_response(
    chat_id: str,
    services: dict = Depends(get_services)
):
    """Regenerate the last AI response in a chat"""
    try:
        # Get chat messages
        messages = await chat_service.get_chat_messages(chat_id)
        
        if len(messages) < 2:
            raise HTTPException(status_code=400, detail="Not enough messages to regenerate")
        
        # Find the last user message
        last_user_message = None
        for msg in reversed(messages):
            if msg["is_user"]:
                last_user_message = msg
                break
        
        if not last_user_message:
            raise HTTPException(status_code=400, detail="No user message found")
        
        # Get chat info to find document_id
        chat_info = await chat_service._load_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Initialize chat service if needed
        if not hasattr(chat_service, 'llm_service') or not chat_service.llm_service.client:
            await chat_service.initialize()
        
        # Remove the last AI response and regenerate
        user_messages_only = [msg for msg in messages if msg["is_user"]]
        await chat_service._save_messages(chat_id, user_messages_only)
        
        # Generate new response
        response = await chat_service.send_message(
            message=last_user_message["content"],
            document_id=chat_info["document_id"],
            chat_id=chat_id,
            vector_service=services["vector_service"],
            embedding_service=services["embedding_service"],
            context_length=5
        )
        
        return {
            "message": "Response regenerated successfully",
            "response": response["response"],
            "sources": response.get("sources", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate response: {e}")
        raise HTTPException(status_code=500, detail="Failed to regenerate response")
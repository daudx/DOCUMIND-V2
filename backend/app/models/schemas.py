from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class DocumentStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentType(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"

# Request Models
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    document_id: str = Field(..., description="Document ID to chat with")
    chat_id: Optional[str] = Field(None, description="Chat session ID")
    context_length: Optional[int] = Field(5, ge=1, le=10, description="Number of context chunks")

class CreateChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Chat title")
    document_id: str = Field(..., description="Document ID")

class DocumentUploadResponse(BaseModel):
    id: str
    name: str
    size: str
    uploaded: str
    status: DocumentStatus
    chunks: int
    type: DocumentType
    processing_time: Optional[float] = None

# Response Models
class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, Any]] = []
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None
    tokens_used: Optional[int] = None

class DocumentInfo(BaseModel):
    id: str
    filename: str
    file_size: int
    content_preview: str
    chunk_count: int
    type: DocumentType
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = {}

class ChatInfo(BaseModel):
    id: str
    title: str
    document_id: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_preview: Optional[str] = None

class MessageInfo(BaseModel):
    id: str
    chat_id: str
    content: str
    is_user: bool
    sources: Optional[List[Dict[str, Any]]] = []
    confidence_score: Optional[float] = None
    created_at: datetime

class DocumentStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    supported_formats: List[str]
    storage_used: str

class ChatStatsResponse(BaseModel):
    total_chats: int
    total_messages: int
    avg_response_time: Optional[float] = None

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    features: Dict[str, str]
    uptime: Optional[str] = None

# Search Models
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    document_id: Optional[str] = None
    limit: Optional[int] = Field(10, ge=1, le=50)
    similarity_threshold: Optional[float] = Field(0.5, ge=0.0, le=1.0)

class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any]

class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total_results: int
    processing_time: float

# Error Models
class ErrorResponse(BaseModel):
    error: str
    detail: str
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ValidationErrorResponse(BaseModel):
    error: str = "validation_error"
    detail: str
    field_errors: List[Dict[str, Any]] = []
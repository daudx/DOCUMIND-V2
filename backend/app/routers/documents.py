import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from models.schemas import DocumentUploadResponse, DocumentStatsResponse, ErrorResponse
from services.document_service import DocumentService

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize document service
document_service = DocumentService()

def get_services(request: Request):
    """Dependency to get services from app state"""
    return {
        "vector_service": request.app.state.vector_service,
        "embedding_service": request.app.state.embedding_service,
        "llm_service": getattr(request.app.state, 'llm_service', None)
    }

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    services: dict = Depends(get_services)
):
    """Upload and process a document"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Read file content
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        # Get services
        vector_service = services["vector_service"]
        embedding_service = services["embedding_service"]
        
        # Initialize LLM service if not available
        if not services.get("llm_service"):
            from services.llm_service import LLMService
            llm_service = LLMService()
            await llm_service.initialize()
        else:
            llm_service = services["llm_service"]
        
        # Process document
        result = await document_service.process_document(
            file_content=file_content,
            filename=file.filename,
            vector_service=vector_service,
            embedding_service=embedding_service,
            llm_service=llm_service
        )
        
        logger.info(f"Document uploaded successfully: {file.filename}")
        return DocumentUploadResponse(**result)
        
    except ValueError as e:
        logger.warning(f"Validation error during upload: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")

@router.get("/documents")
async def get_documents():
    """Get all uploaded documents"""
    try:
        documents = await document_service.get_all_documents()
        
        # Format response
        formatted_docs = []
        for doc in documents:
            formatted_doc = {
                "id": doc["id"],
                "name": doc["filename"],
                "size": f"{doc['file_size'] / (1024 * 1024):.2f} MB",
                "uploaded": doc["created_at"][:19].replace('T', ' '),  # Format datetime
                "status": doc["status"],
                "chunks": doc["chunk_count"],
                "type": doc["type"]
            }
            formatted_docs.append(formatted_doc)
        
        return formatted_docs
        
    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents")

@router.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get a specific document by ID"""
    try:
        document = await document_service.get_document_by_id(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    services: dict = Depends(get_services)
):
    """Delete a document and all its data"""
    try:
        # Check if document exists
        document = await document_service.get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete document
        vector_service = services["vector_service"]
        success = await document_service.delete_document(document_id, vector_service)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete document")
        
        return {"message": "Document deleted successfully", "document_id": document_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")

@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    services: dict = Depends(get_services)
):
    """Get all chunks for a document"""
    try:
        # Check if document exists
        document = await document_service.get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get chunks from vector service
        vector_service = services["vector_service"]
        chunks = await vector_service.get_document_chunks(document_id)
        
        return {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "chunks": chunks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chunks for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document chunks")

@router.get("/documents/{document_id}/summary")
async def get_document_summary(
    document_id: str,
    services: dict = Depends(get_services)
):
    """Get AI-generated summary of a document"""
    try:
        # Check if document exists
        document = await document_service.get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get document chunks
        vector_service = services["vector_service"]
        chunks = await vector_service.get_document_chunks(document_id)
        
        if not chunks:
            raise HTTPException(status_code=404, detail="No content found for document")
        
        # Initialize LLM service if needed
        if not services.get("llm_service"):
            from services.llm_service import LLMService
            llm_service = LLMService()
            await llm_service.initialize()
        else:
            llm_service = services["llm_service"]
        
        # Generate summary
        chunk_texts = [chunk["content"] for chunk in chunks[:10]]  # First 10 chunks
        summary = await llm_service.summarize_document(chunk_texts)
        
        return {
            "document_id": document_id,
            "document_name": document["filename"],
            "summary": summary,
            "chunks_analyzed": len(chunk_texts)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate summary for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate document summary")

@router.get("/documents/{document_id}/keywords")
async def get_document_keywords(
    document_id: str,
    services: dict = Depends(get_services)
):
    """Get AI-extracted keywords from a document"""
    try:
        # Check if document exists
        document = await document_service.get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get document chunks
        vector_service = services["vector_service"]
        chunks = await vector_service.get_document_chunks(document_id)
        
        if not chunks:
            raise HTTPException(status_code=404, detail="No content found for document")
        
        # Initialize LLM service if needed
        if not services.get("llm_service"):
            from services.llm_service import LLMService
            llm_service = LLMService()
            await llm_service.initialize()
        else:
            llm_service = services["llm_service"]
        
        # Extract keywords
        content = " ".join([chunk["content"] for chunk in chunks[:5]])  # First 5 chunks
        keywords = await llm_service.extract_keywords(content)
        
        return {
            "document_id": document_id,
            "document_name": document["filename"],
            "keywords": keywords,
            "chunks_analyzed": min(5, len(chunks))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extract keywords for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract keywords")

@router.get("/stats", response_model=DocumentStatsResponse)
async def get_document_stats(services: dict = Depends(get_services)):
    """Get document processing statistics"""
    try:
        # Get document stats
        documents = await document_service.get_all_documents()
        
        # Get vector database stats
        vector_service = services["vector_service"]
        vector_stats = await vector_service.get_collection_stats()
        
        # Calculate storage used (rough estimate)
        total_size = sum(doc.get("file_size", 0) for doc in documents)
        storage_used = f"{total_size / (1024 * 1024):.2f} MB"
        
        return DocumentStatsResponse(
            total_documents=len(documents),
            total_chunks=vector_stats.get("total_chunks", 0),
            supported_formats=["PDF", "TXT", "DOCX"],
            storage_used=storage_used
        )
        
    except Exception as e:
        logger.error(f"Failed to get document stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    services: dict = Depends(get_services)
):
    """Reprocess a document (useful after changing chunk settings)"""
    try:
        # Check if document exists
        document = await document_service.get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # This would require storing original file content
        # For now, return not implemented
        raise HTTPException(
            status_code=501, 
            detail="Document reprocessing not implemented. Please re-upload the document."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reprocess document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reprocess document")
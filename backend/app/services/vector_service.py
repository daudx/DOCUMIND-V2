import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import numpy as np
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class VectorService:
    def __init__(self):
        self.client = None
        self.collection = None
        self.collection_name = "documents"
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def initialize(self):
        """Initialize ChromaDB client and collection"""
        try:
            # Create data directory if it doesn't exist
            data_dir = os.getenv("CHROMA_DATA_DIR", "./data/chroma")
            os.makedirs(data_dir, exist_ok=True)
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=data_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name
                )
                logger.info(f"Loaded existing collection with {self.collection.count()} documents")
            except Exception:
                # Create new collection if it doesn't exist
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Document chunks for RAG"}
                )
                logger.info("Created new document collection")
                
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {e}")
            raise
    
    async def add_documents(
        self,
        document_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]]
    ) -> bool:
        """Add document chunks to vector database"""
        try:
            # Prepare data for ChromaDB
            ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            
            # Ensure metadata includes document_id
            for i, meta in enumerate(metadata):
                meta.update({
                    "document_id": document_id,
                    "chunk_index": i,
                    "created_at": datetime.now().isoformat()
                })
            
            # Add to collection in thread executor
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._add_to_collection,
                ids, embeddings, metadata, chunks
            )
            
            logger.info(f"Added {len(chunks)} chunks for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False
    
    def _add_to_collection(self, ids, embeddings, metadata, documents):
        """Thread-safe method to add to collection"""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadata,
            documents=documents
        )
    
    async def search_similar(
        self,
        query_embedding: List[float],
        document_id: Optional[str] = None,
        n_results: int = 5,
        similarity_threshold: float = 0.5
    ) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Search for similar document chunks"""
        try:
            # Prepare where clause for filtering
            where_clause = {}
            if document_id:
                where_clause["document_id"] = document_id
            
            # Perform search in thread executor
            results = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._query_collection,
                query_embedding, n_results, where_clause
            )
            
            # Process results
            search_results = []
            similarities = []
            
            if results and 'documents' in results:
                for i in range(len(results['documents'][0])):
                    # Calculate similarity score (ChromaDB returns distances)
                    distance = results['distances'][0][i]
                    similarity = 1 - distance  # Convert distance to similarity
                    
                    if similarity >= similarity_threshold:
                        result = {
                            'id': results['ids'][0][i],
                            'content': results['documents'][0][i],
                            'metadata': results['metadatas'][0][i],
                            'similarity_score': similarity
                        }
                        search_results.append(result)
                        similarities.append(similarity)
            
            return search_results, similarities
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return [], []
    
    def _query_collection(self, query_embedding, n_results, where_clause):
        """Thread-safe method to query collection"""
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_clause if where_clause else None,
            include=['documents', 'metadatas', 'distances']
        )
    
    async def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document"""
        try:
            results = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._get_document_chunks,
                document_id
            )
            
            chunks = []
            if results and 'documents' in results:
                for i in range(len(results['documents'])):
                    chunk = {
                        'id': results['ids'][i],
                        'content': results['documents'][i],
                        'metadata': results['metadatas'][i]
                    }
                    chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to get document chunks: {e}")
            return []
    
    def _get_document_chunks(self, document_id):
        """Thread-safe method to get document chunks"""
        return self.collection.get(
            where={"document_id": document_id},
            include=['documents', 'metadatas']
        )
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete all chunks for a document"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._delete_document,
                document_id
            )
            
            logger.info(f"Deleted document {document_id} from vector database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False
    
    def _delete_document(self, document_id):
        """Thread-safe method to delete document"""
        self.collection.delete(
            where={"document_id": document_id}
        )
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            count = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.collection.count()
            )
            
            return {
                "total_chunks": count,
                "collection_name": self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total_chunks": 0, "collection_name": self.collection_name}
    
    async def search_across_documents(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Search across all documents"""
        results, similarities = await self.search_similar(
            query_embedding=query_embedding,
            document_id=None,  # Search all documents
            n_results=n_results,
            similarity_threshold=similarity_threshold
        )
        return results
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)
            logger.info("Vector service cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def reset_collection(self):
        """Reset the entire collection (for testing)"""
        try:
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.client.delete_collection(self.collection_name)
            )
            
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Document chunks for RAG"}
            )
            
            logger.info("Collection reset successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            return False
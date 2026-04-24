import os
import logging
from typing import List, Dict, Any, Optional
import asyncio
from groq import Groq
import time

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama3-8b-8192")
        self.client = None
        self.max_tokens = int(os.getenv("MAX_TOKENS", "1000"))
        self.temperature = float(os.getenv("TEMPERATURE", "0.1"))

    async def initialize(self):
        """Initialize the Groq client"""
        try:
            if not self.api_key:
                logger.error("GROQ_API_KEY not found in environment")
                raise ValueError("GROQ_API_KEY is required")
            
            self.client = Groq(api_key=self.api_key)
            logger.info(f"Groq client initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise

    async def generate_response(self, query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a response using RAG context"""
        try:
            # Prepare context string
            context_text = "\n\n".join([
                f"Source [{i+1}] (from {chunk['metadata'].get('filename', 'unknown')}):\n{chunk['content']}"
                for i, chunk in enumerate(context_chunks)
            ])

            system_prompt = f"""You are DocuMind, an intelligent document assistant. 
Use the following pieces of retrieved context to answer the user's question. 
If the answer is not in the context, say that you don't know based on the provided documents.
Always cite your sources using the [Source X] format when applicable.

Context:
{context_text}
"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]

            start_time = time.time()
            
            # Use asyncio to run the synchronous groq call
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )
            )
            
            execution_time = time.time() - start_time
            
            ai_response = response.choices[0].message.content
            
            # Extract sources used
            sources = []
            for i, chunk in enumerate(context_chunks):
                if f"[Source {i+1}]" in ai_response:
                    sources.append({
                        "id": chunk.get("id"),
                        "filename": chunk["metadata"].get("filename"),
                        "index": i + 1
                    })

            return {
                "response": ai_response,
                "sources": sources,
                "model_used": self.model,
                "tokens_used": response.usage.total_tokens,
                "execution_time": execution_time
            }

        except Exception as e:
            logger.error(f"Failed to generate LLM response: {e}")
            raise

    async def generate_title(self, text: str) -> str:
        """Generate a short, descriptive title for a document"""
        try:
            prompt = f"Generate a short, descriptive title (max 6 words) for the following text content:\n\n{text[:2000]}"
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.3
                )
            )
            
            title = response.choices[0].message.content.strip().strip('"')
            return title
            
        except Exception as e:
            logger.error(f"Failed to generate title: {e}")
            return "Untitled Document"

    async def summarize_document(self, chunks: List[str]) -> str:
        """Generate a summary for a list of document chunks"""
        try:
            content = "\n\n".join(chunks)
            prompt = f"Summarize the following document content in 3-5 bullet points focusing on key findings and main topics:\n\n{content[:4000]}"
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                    temperature=0.2
                )
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return "Summary generation failed."

    async def extract_keywords(self, content: str) -> List[str]:
        """Extract key topics/keywords from content"""
        try:
            prompt = f"Extract the top 10 most important keywords or short phrases from the following text. Return them as a comma-separated list:\n\n{content[:3000]}"
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.1
                )
            )
            
            keyword_text = response.choices[0].message.content.strip()
            keywords = [k.strip() for k in keyword_text.split(',')]
            return keywords[:10]
            
        except Exception as e:
            logger.error(f"Failed to extract keywords: {e}")
            return []

    async def cleanup(self):
        """Cleanup resources"""
        # Groq client doesn't explicitly need cleanup but we can null it
        self.client = None
        logger.info("LLM service cleaned up")

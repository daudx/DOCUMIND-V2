import os
import logging
from typing import Optional, Dict, Any
import aiofiles
import json

logger = logging.getLogger(__name__)


async def init_db():
    """Initialize database directories and files"""
    try:
        # Create necessary directories
        directories = [
            "./data",
            "./data/uploads",
            "./data/chroma",
            "./data/uploads/chats",
            "./temp",
            "./logs",
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Directory ensured: {directory}")

        # Create config file if it doesn't exist
        config_file = "./data/config.json"
        if not os.path.exists(config_file):
            default_config = {
                "version": "2.0.0",
                "initialized_at": "2024-01-01T00:00:00",
                "settings": {
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                    "max_file_size_mb": 50,
                    "supported_formats": ["pdf", "txt", "docx"],
                },
            }

            async with aiofiles.open(config_file, "w") as f:
                await f.write(json.dumps(default_config, indent=2))

            logger.info("Default config created")

        logger.info("Database initialization completed")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def get_db_connection():
    """Get database connection (placeholder for future DB integration)"""
    # This is a placeholder for future database integration
    # Currently using file-based storage
    return None


async def save_json_data(filepath: str, data: Dict[str, Any]):
    """Save data to JSON file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        async with aiofiles.open(filepath, "w") as f:
            await f.write(json.dumps(data, indent=2, default=str))

    except Exception as e:
        logger.error(f"Failed to save JSON data to {filepath}: {e}")
        raise


async def load_json_data(filepath: str) -> Optional[Dict[str, Any]]:
    """Load data from JSON file"""
    try:
        if not os.path.exists(filepath):
            return None

        async with aiofiles.open(filepath, "r") as f:
            content = await f.read()
            return json.loads(content)

    except Exception as e:
        logger.error(f"Failed to load JSON data from {filepath}: {e}")
        return None


async def cleanup_temp_files():
    """Clean up temporary files"""
    try:
        temp_dir = "./temp"
        if os.path.exists(temp_dir):
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {filename}: {e}")

        logger.info("Temporary files cleaned up")

    except Exception as e:
        logger.error(f"Failed to cleanup temp files: {e}")


async def get_system_stats() -> Dict[str, Any]:
    """Get system statistics"""
    try:
        stats = {"storage": {}, "files": {}, "system": {}}

        # Calculate storage usage
        data_dir = "./data"
        if os.path.exists(data_dir):
            total_size = 0
            file_count = 0

            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        total_size += size
                        file_count += 1
                    except:
                        continue

            stats["storage"]["total_size_mb"] = total_size / (1024 * 1024)
            stats["files"]["total_files"] = file_count

        # Get upload statistics
        uploads_dir = "./data/uploads"
        if os.path.exists(uploads_dir):
            document_count = len(
                [f for f in os.listdir(uploads_dir) if f.endswith("_info.json")]
            )
            stats["files"]["documents"] = document_count

        # Get chat statistics
        chats_dir = "./data/uploads/chats"
        if os.path.exists(chats_dir):
            chat_count = len(
                [f for f in os.listdir(chats_dir) if f.endswith("_info.json")]
            )
            stats["files"]["chats"] = chat_count

        return stats

    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        return {"error": str(e)}

"""Supabase client initialization and utilities"""
import logging
from typing import Optional
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

# Global Supabase admin client instance
_supabase_admin_client: Optional[Client] = None


def get_supabase_admin_client() -> Client:
    """
    Get or create Supabase admin client with service role key.
    
    This client bypasses RLS policies and should be used for admin operations only.
    
    Returns:
        Supabase admin client instance
    """
    global _supabase_admin_client
    
    if _supabase_admin_client is None:
        try:
            _supabase_admin_client = create_client(
                settings.supabase_url,
                settings.supabase_service_key
            )
            logger.info("Supabase admin client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase admin client: {e}")
            raise
    
    return _supabase_admin_client


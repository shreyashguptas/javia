"""Supabase client initialization and utilities"""
import logging
from typing import Optional
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

# Global Supabase client instances
_supabase_client: Optional[Client] = None
_supabase_admin_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create Supabase client with anon key.
    
    This client is used for standard operations that respect RLS policies.
    
    Returns:
        Supabase client instance
    """
    global _supabase_client
    
    if _supabase_client is None:
        try:
            _supabase_client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    return _supabase_client


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


def close_supabase_clients():
    """Close Supabase client connections"""
    global _supabase_client, _supabase_admin_client
    
    # Supabase Python client doesn't require explicit cleanup
    # but we'll reset the instances for clean shutdown
    _supabase_client = None
    _supabase_admin_client = None
    logger.info("Supabase clients closed")


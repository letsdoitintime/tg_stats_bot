"""Base repository with common database operations.

This module provides a generic base repository class with standard CRUD operations
that can be extended by specific repository implementations.
"""

from typing import Generic, TypeVar, Type, Optional, List, Any, Dict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations.
    
    This generic repository provides standard database operations that can be
    inherited by model-specific repositories. It uses SQLAlchemy's async API.
    
    Type Parameters:
        ModelType: SQLAlchemy model class bound to Base
        
    Example:
        class UserRepository(BaseRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(User, session)
                
            async def find_by_username(self, username: str) -> Optional[User]:
                # Custom query method
                pass
    """
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """Initialize repository with model class and database session.
        
        Args:
            model: SQLAlchemy model class for this repository
            session: Async database session for executing queries
        """
        self.model = model
        self.session = session
    
    async def get_by_id(self, id_value: Any) -> Optional[ModelType]:
        """Get a single record by its primary key ID.
        
        Args:
            id_value: Primary key value to search for
            
        Returns:
            Model instance if found, None otherwise
            
        Note:
            This assumes the model has an 'id' attribute as primary key.
            Override this method if your model uses a different primary key.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id_value)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        order_by: Optional[Any] = None
    ) -> List[ModelType]:
        """Get all records with pagination and optional ordering.
        
        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return
            order_by: Optional SQLAlchemy ordering expression
            
        Returns:
            List of model instances
        """
        query = select(self.model).offset(skip).limit(limit)
        if order_by is not None:
            query = query.order_by(order_by)
            
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record with the given attributes.
        
        Args:
            **kwargs: Model attributes as keyword arguments
            
        Returns:
            Created model instance
            
        Note:
            This only flushes the instance to the database. Call session.commit()
            to persist the changes.
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
    
    async def update(self, instance: ModelType, **kwargs: Any) -> ModelType:
        """Update an existing record with new attribute values.
        
        Args:
            instance: Model instance to update
            **kwargs: Attributes to update as keyword arguments
            
        Returns:
            Updated model instance
            
        Note:
            This only flushes changes to the database. Call session.commit()
            to persist the changes.
        """
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
    
    async def delete(self, instance: ModelType) -> None:
        """Delete a record from the database.
        
        Args:
            instance: Model instance to delete
            
        Note:
            This only marks the instance for deletion. Call session.commit()
            to persist the changes.
        """
        await self.session.delete(instance)
        await self.session.flush()
    
    async def count(self) -> int:
        """Count total number of records.
        
        Returns:
            Total count of records for this model
        """
        result = await self.session.execute(
            select(self.model).with_only_columns(func.count())
        )
        return result.scalar_one()
    
    async def exists(self, id_value: Any) -> bool:
        """Check if a record exists by ID.
        
        Args:
            id_value: Primary key value to check
            
        Returns:
            True if record exists, False otherwise
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id_value).limit(1)
        )
        return result.scalar_one_or_none() is not None
    
    async def commit(self) -> None:
        """Commit the current transaction.
        
        Note:
            It's generally better to manage transactions at a higher level
            (e.g., in services or handlers) rather than in repositories.
        """
        await self.session.commit()
    
    async def rollback(self) -> None:
        """Rollback the current transaction.
        
        Note:
            It's generally better to manage transactions at a higher level
            (e.g., in services or handlers) rather than in repositories.
        """
        await self.session.rollback()

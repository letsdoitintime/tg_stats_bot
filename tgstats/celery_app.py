"""Celery app initialization for tgstats."""

from .celery_tasks import celery_app

__all__ = ["celery_app"]

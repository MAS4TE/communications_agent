"""Interfaces (Protocols) for core.db."""

from .database import Reader, Writer, Confirmable, DatabaseIO

__all__ = ["Reader", "Writer", "Confirmable", "DatabaseIO"]

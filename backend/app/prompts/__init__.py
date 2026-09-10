"""Prompts versionados y separados por responsabilidad."""

from .messages import build_gemini_request, build_ollama_messages

__all__ = ["build_gemini_request", "build_ollama_messages"]

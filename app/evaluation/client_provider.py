from app.evaluation.llm_client import OpenAILLMClient
from app.evaluation.llm_protocol import LLMChatClient


def get_default_llm_client() -> LLMChatClient:
    """Return the default client used for the stage-1/2 rubric pipeline."""
    return OpenAILLMClient()


def get_default_rag_client() -> LLMChatClient:
    """Return the default client used for RAG metric computations."""
    return OpenAILLMClient()

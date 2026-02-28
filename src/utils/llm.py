from typing import Dict, List, Any
import os
from langchain_openai import ChatOpenAI
try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

def get_model():
    """
    Returns a configured Chat Model (OpenAI or Ollama) with optional fallback.
    Reads from environment variables:
    - JUDGE_PROVIDER: 'openai' (default) or 'ollama'
    - JUDGE_MODEL: Model name
    - JUDGE_FALLBACK_PROVIDER: Optional fallback provider
    - JUDGE_FALLBACK_MODEL: Optional fallback model name
    """
    provider = os.getenv("JUDGE_PROVIDER", "openai").lower()
    model_name = os.getenv("JUDGE_MODEL")
    
    primary_model = None

    # Determine Ollama Base URL (default is http://localhost:11434)
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    if provider == "ollama":
        if not ChatOllama:
            raise ImportError("langchain-ollama is not installed. Please run `pip install langchain-ollama`.")
        # If no model provided, default to llama3.2
        target_model = model_name if model_name else "llama3.2:latest"
        print(f"Using Primary Model: Ollama / {target_model} at {ollama_base_url}")
        primary_model = ChatOllama(model=target_model, base_url=ollama_base_url, temperature=0)
    else:
        # Default to OpenAI
        target_model = model_name if model_name else "gpt-4o"
        # Only print if not already configured to avoid spam
        # print(f"Using Primary Model: OpenAI / {target_model}")
        primary_model = ChatOpenAI(model=target_model, temperature=0)

    # Configure Fallback
    fallback_provider = os.getenv("JUDGE_FALLBACK_PROVIDER")
    fallback_model_name = os.getenv("JUDGE_FALLBACK_MODEL")

    if fallback_provider:
        fallback_model = None
        if fallback_provider.lower() == "ollama":
             if ChatOllama:
                fb_model = fallback_model_name if fallback_model_name else "llama3.2:latest"
                print(f"  Fallback: Ollama / {fb_model}")
                fallback_model = ChatOllama(model=fb_model, base_url=ollama_base_url, temperature=0)
        elif fallback_provider.lower() == "openai":
             fb_model = fallback_model_name if fallback_model_name else "gpt-3.5-turbo"
             print(f"  Fallback: OpenAI / {fb_model}")
             fallback_model = ChatOpenAI(model=fb_model, temperature=0)
        
        if fallback_model:
            primary_model = primary_model.with_fallbacks([fallback_model])

    return primary_model

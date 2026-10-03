import os

from langchain_openai import ChatOpenAI


def my_llm(llm_type):
    if llm_type == 'ollama':
        base = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434/v1')
        key = os.getenv('OLLAMA_API_KEY', 'ollama')
        model = os.getenv('OLLAMA_CHAT_MODEL', 'llama3.1:latest')
    elif llm_type == 'oneapi':
        base = os.getenv('ONEAPI_API_BASE', 'http://localhost:3000/v1')
        key = os.getenv('ONEAPI_API_KEY')
        model = os.getenv('ONEAPI_CHAT_MODEL', 'qwen-max')
    elif llm_type == 'openai':
        base = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
        key = os.getenv('OPENAI_API_KEY')
        model = os.getenv('OPENAI_CHAT_MODEL', 'gpt-4o-mini')
    else:
        raise ValueError('LLM_TYPE 须为 openai、oneapi 或 ollama')
    if not key:
        raise ValueError('请先在环境变量中配置所选模型服务的 API Key')
    return ChatOpenAI(base_url=base, api_key=key, model=model, timeout=60, max_retries=2)

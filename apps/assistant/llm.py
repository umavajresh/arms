import json
import logging
from dataclasses import dataclass

import requests
from django.conf import settings

from .text import sanitize_text
from .tools import travel_tools

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ("openrouter", "groq", "huggingface", "openai")
AUTO_PROVIDER = "auto"
ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "huggingface": "https://router.huggingface.co/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}
DEFAULT_MODELS = {
    "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
    "groq": "llama-3.3-70b-versatile",
    "huggingface": "meta-llama/Llama-3.2-3B-Instruct",
    "openai": "gpt-4o-mini",
}
KEY_PREFIXES = (("sk-or-", "openrouter"), ("gsk_", "groq"), ("hf_", "huggingface"))
MAX_TOOL_CALLS = 3
MAX_TOOL_PAYLOAD = 4000
MAX_MODEL_NAME = 128
REQUEST_TIMEOUT = (5, 22)


def provider_for_key(key):
    for prefix, provider in KEY_PREFIXES:
        if key.startswith(prefix):
            return provider
    return "openai"


def is_valid_model_name(model):
    return len(model) <= MAX_MODEL_NAME and not any(char in model for char in "\r\n")


@dataclass(frozen=True)
class ProviderConfiguration:
    key: str
    provider: str
    source: str

    @classmethod
    def resolve(cls, api_key=None, provider=None):
        selected = (provider or AUTO_PROVIDER).strip().lower()
        if selected not in (*SUPPORTED_PROVIDERS, AUTO_PROVIDER):
            raise ValueError("Unsupported AI provider.")
        configured = settings.ARMS_AI_PROVIDER_API_KEYS
        fallback = settings.ARMS_AI_FALLBACK_API_KEY
        if selected != AUTO_PROVIDER:
            key = api_key or configured.get(selected) or fallback
            source = "session" if api_key else ("environment" if key else "fallback")
            return cls(key or "", selected, source)
        if api_key:
            return cls(api_key, provider_for_key(api_key), "session")
        for candidate in SUPPORTED_PROVIDERS:
            if configured.get(candidate):
                return cls(configured[candidate], candidate, "environment")
        if fallback:
            return cls(fallback, provider_for_key(fallback), "environment")
        return cls("", AUTO_PROVIDER, "fallback")

    def status(self):
        return {
            "has_key": bool(self.key),
            "provider": self.provider,
            "source": self.source,
        }


def get_llm_provider_status(api_key=None, provider=None):
    return ProviderConfiguration.resolve(api_key, provider).status()


class ChatCompletionClient:
    def __init__(self, configuration, model=None):
        self.configuration = configuration
        self.model = (model or "default").strip()

    def resolved_model(self):
        if self.model == "default":
            return DEFAULT_MODELS[self.configuration.provider]
        return self.model

    def headers(self):
        headers = {
            "Authorization": "Bearer %s" % self.configuration.key,
            "Content-Type": "application/json",
        }
        if self.configuration.provider == "openrouter":
            headers["HTTP-Referer"] = settings.ARMS_SITE_URL
            headers["X-Title"] = "ARMS Travel Assistant"
        return headers

    def request(self, conversation, allow_tools):
        payload = {
            "model": self.resolved_model(),
            "messages": conversation,
            "max_tokens": 1200,
            "temperature": 0.75,
        }
        if allow_tools:
            payload["tools"] = travel_tools.model_definitions()
            payload["tool_choice"] = "auto"
        provider = self.configuration.provider
        try:
            response = requests.post(
                ENDPOINTS[provider],
                json=payload,
                headers=self.headers(),
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code != 200:
                logger.warning(
                    "AI provider request failed: provider=%s status=%s",
                    provider,
                    response.status_code,
                )
                return None
            data = response.json()
            message = data["choices"][0]["message"]
        except (requests.RequestException, ValueError, LookupError, TypeError):
            logger.warning("AI provider request could not be completed: %s", provider)
            return None
        if not isinstance(message, dict):
            logger.warning("AI provider returned a malformed response: %s", provider)
            return None
        return message

    def complete(self, messages):
        if not self.configuration.key or not is_valid_model_name(self.model):
            return None
        reply = self.request(messages, allow_tools=True)
        if reply is None:
            return None
        tool_calls = reply.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            follow_up = self._tool_follow_up(messages, reply, tool_calls)
            if follow_up is None:
                return None
            reply = self.request(follow_up, allow_tools=False)
            if reply is None:
                return None
        return self._content(reply)

    def _tool_follow_up(self, messages, reply, tool_calls):
        if len(tool_calls) > MAX_TOOL_CALLS:
            logger.warning("AI provider requested too many travel tools.")
            return None
        safe_calls, tool_messages = [], []
        for call in tool_calls:
            parsed = self._parse_tool_call(call)
            if parsed is None:
                logger.warning("AI provider requested an invalid travel tool.")
                return None
            call_id, name, raw_arguments, arguments = parsed
            result = travel_tools.execute(name, arguments)
            safe_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": raw_arguments},
                }
            )
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(result, default=str)[:MAX_TOOL_PAYLOAD],
                }
            )
        return [
            *messages,
            {
                "role": "assistant",
                "content": reply.get("content"),
                "tool_calls": safe_calls,
            },
            *tool_messages,
        ]

    def _parse_tool_call(self, call):
        if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
            return None
        call_id = call.get("id")
        name = call["function"].get("name")
        raw_arguments = call["function"].get("arguments")
        if (
            not isinstance(call_id, str)
            or not call_id
            or len(call_id) > 128
            or name not in travel_tools.model_tool_names()
            or not isinstance(raw_arguments, str)
            or len(raw_arguments) > MAX_TOOL_PAYLOAD
        ):
            return None
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return None
        if not isinstance(arguments, dict):
            return None
        return call_id, name, raw_arguments, arguments

    def _content(self, reply):
        content = reply.get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            logger.warning("AI provider returned an empty or malformed response.")
            return None
        return sanitize_text(content.strip())


def call_external_llm(messages, api_key=None, provider=None, model=None):
    configuration = ProviderConfiguration.resolve(api_key, provider)
    return ChatCompletionClient(configuration, model).complete(messages)

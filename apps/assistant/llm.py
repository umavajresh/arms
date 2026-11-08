import json
import logging
import re
from dataclasses import dataclass

import requests
from django.conf import settings

from .text import sanitize_text
from .tools import travel_tools

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ("openrouter", "groq", "huggingface", "openai")
ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "huggingface": "https://router.huggingface.co/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}
DEFAULT_MODELS = {
    "openrouter": "openrouter/free",
    "groq": "llama-3.3-70b-versatile",
    "huggingface": "meta-llama/Llama-3.2-3B-Instruct",
    "openai": "gpt-4o-mini",
}
KEY_PREFIXES = (("sk-or-", "openrouter"), ("gsk_", "groq"), ("hf_", "huggingface"))
TOOL_INCOMPATIBLE_STATUSES = frozenset({400, 404, 422})
MAX_TOOL_CALLS = 3
MAX_REPLY_TOKENS = 2000
EMPTY_REPLY_ATTEMPTS = 2
MAX_TOOL_PAYLOAD = 4000
MAX_LOGGED_ERROR = 300
LEAKED_TOOL_MARKUP = re.compile(r"<\s*/?\s*\w*(invoke|function_call|tool_call)\b")
REQUEST_TIMEOUT = (5, 30)


def provider_for_key(key):
    for prefix, provider in KEY_PREFIXES:
        if key.startswith(prefix):
            return provider
    return "openai"


@dataclass(frozen=True)
class ProviderConfiguration:
    key: str
    provider: str
    model: str

    @classmethod
    def from_settings(cls):
        configured = settings.ARMS_AI_PROVIDER_API_KEYS
        for provider in SUPPORTED_PROVIDERS:
            if configured.get(provider):
                return cls.for_provider(configured[provider], provider)
        fallback = settings.ARMS_AI_FALLBACK_API_KEY
        if fallback:
            return cls.for_provider(fallback, provider_for_key(fallback))
        return cls(key="", provider="", model="")

    @classmethod
    def for_provider(cls, key, provider):
        return cls(
            key=key,
            provider=provider,
            model=settings.ARMS_AI_MODEL or DEFAULT_MODELS[provider],
        )

    @property
    def is_configured(self):
        return bool(self.key)


class EmptyReply(Exception):
    pass


@dataclass(frozen=True)
class ProviderReply:
    message: dict | None
    status: int | None

    @property
    def rejected_tools(self):
        return self.message is None and self.status in TOOL_INCOMPATIBLE_STATUSES


class ChatCompletionClient:
    def __init__(self, configuration):
        self.configuration = configuration

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
            "model": self.configuration.model,
            "messages": conversation,
            "max_tokens": MAX_REPLY_TOKENS,
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
        except requests.RequestException:
            logger.warning("AI provider could not be reached: %s", provider)
            return ProviderReply(None, None)
        if response.status_code != 200:
            logger.warning(
                "AI provider request failed: provider=%s model=%s status=%s detail=%s",
                provider,
                self.configuration.model,
                response.status_code,
                self._error_detail(response),
            )
            return ProviderReply(None, response.status_code)
        try:
            message = response.json()["choices"][0]["message"]
        except (ValueError, LookupError, TypeError):
            message = None
        if not isinstance(message, dict):
            logger.warning("AI provider returned a malformed response: %s", provider)
            return ProviderReply(None, response.status_code)
        return ProviderReply(message, response.status_code)

    def _error_detail(self, response):
        try:
            error = response.json().get("error")
        except (ValueError, AttributeError):
            return response.text[:MAX_LOGGED_ERROR]
        if isinstance(error, dict):
            return str(error.get("message", ""))[:MAX_LOGGED_ERROR]
        return str(error)[:MAX_LOGGED_ERROR]

    def complete(self, messages):
        if not self.configuration.is_configured:
            return None
        for attempt in range(1, EMPTY_REPLY_ATTEMPTS + 1):
            try:
                return self._attempt(messages)
            except EmptyReply:
                logger.warning(
                    "AI provider returned an empty reply (attempt %d of %d).",
                    attempt,
                    EMPTY_REPLY_ATTEMPTS,
                )
        return None

    def _attempt(self, messages):
        reply = self.request(messages, allow_tools=True)
        if reply.rejected_tools:
            logger.warning("Retrying the AI request without ARMS travel tools.")
            reply = self.request(messages, allow_tools=False)
        if reply.message is None:
            return None
        tool_calls = reply.message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            follow_up = self._tool_follow_up(messages, reply.message, tool_calls)
            if follow_up is None:
                return None
            reply = self.request(follow_up, allow_tools=False)
            if reply.message is None:
                return None
        content = self._content(reply.message)
        if content is None:
            raise EmptyReply
        return content

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
            return None
        if LEAKED_TOOL_MARKUP.search(content):
            return None
        return sanitize_text(content.strip())


def call_external_llm(messages):
    return ChatCompletionClient(ProviderConfiguration.from_settings()).complete(
        messages
    )

import json
import logging

from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import PageMixin, public_view
from apps.core.rate_limit import RateLimiter

from .conversation import ChatSession
from .inventory import search_real_flights
from .llm import AUTO_PROVIDER, SUPPORTED_PROVIDERS, get_llm_provider_status
from .preferences import extract_travel_preferences
from .responder import get_travel_response
from .text import SUPPORTED_LANGUAGES
from .tools import execute_travel_tool

logger = logging.getLogger(__name__)

chat_limiter = RateLimiter("ai-chat", limit=30, window_seconds=60)
MAX_MESSAGE_LENGTH = 2000
MAX_TOOL_ARGUMENTS_LENGTH = 4000
MAX_API_KEY_LENGTH = 512
MAX_MODEL_LENGTH = 128
INVENTORY_UNAVAILABLE_NOTE = (
    "\n\nARMS flight inventory could not be checked for this request. "
    "No flight availability or fare is confirmed."
)
RESPONSE_UNAVAILABLE = (
    "I could not generate the full travel plan right now. "
    "Please try again, or search the flight inventory directly."
)


def chat_failure(message, status=400):
    return JsonResponse({"status": "failed", "message": message}, status=status)


def chat_success(**payload):
    return JsonResponse({"status": "success", **payload})


def _has_line_break(value):
    return any(char in value for char in "\r\n")


@public_view
class TravelChatView(PageMixin, TemplateView):
    template_name = "assistant/chat.html"
    page_title = "AI Travel Assistant"
    assistant_launcher = False


@public_view
class TravelChatApiView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        self.chat = ChatSession(request.session)
        actions = {
            "save_ai_settings": self.save_settings,
            "get_ai_status": self.provider_status,
            "clear_chat": self.clear_chat,
        }
        action = actions.get(request.POST.get("action"))
        if action is not None:
            return action()
        if chat_limiter.is_limited(request):
            return chat_failure(
                "You have sent too many messages. "
                "Please wait one minute and try again.",
                status=429,
            )
        if request.POST.get("tool_name"):
            return self.run_tool()
        return self.answer()

    def save_settings(self):
        api_key = self.request.POST.get("api_key", "").strip()
        provider = self.request.POST.get("provider", AUTO_PROVIDER).strip().lower()
        model = self.request.POST.get("model", "").strip()
        if provider not in (*SUPPORTED_PROVIDERS, AUTO_PROVIDER):
            return chat_failure("Choose a supported AI provider.")
        if (
            len(api_key) > MAX_API_KEY_LENGTH
            or _has_line_break(api_key)
            or len(model) > MAX_MODEL_LENGTH
            or _has_line_break(model)
        ):
            return chat_failure("The API key or model name is invalid.")
        self.chat.save_settings(
            api_key=api_key,
            provider=provider,
            model=model,
            clear_key=self.request.POST.get("clear_key") == "1",
        )
        return chat_success(message="AI configuration saved.")

    def provider_status(self):
        status = get_llm_provider_status(
            api_key=self.chat.api_key, provider=self.chat.provider
        )
        return chat_success(**status, model=self.chat.model or "default")

    def clear_chat(self):
        self.chat.clear_conversation()
        return chat_success(message="Conversation cleared.")

    def run_tool(self):
        raw_arguments = self.request.POST.get("tool_args", "{}")
        if len(raw_arguments) > MAX_TOOL_ARGUMENTS_LENGTH:
            return chat_failure("The requested tool input is too large.")
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return chat_failure("The requested tool input is not valid JSON.")
        if not isinstance(arguments, dict):
            return chat_failure("Tool input must be a JSON object.")
        try:
            result = execute_travel_tool(self.request.POST["tool_name"], arguments)
        except Exception:
            logger.exception("Travel tool request failed")
            return chat_failure(
                "The requested travel data is temporarily unavailable.", status=503
            )
        if isinstance(result, dict) and result.get("error"):
            return chat_failure(result["error"])
        return chat_success(tool_result=result)

    def answer(self):
        message = self.request.POST.get("message", "").strip()
        language = (self.request.POST.get("language") or "en").strip().lower()
        if not message:
            return chat_failure("Please type a travel question first.")
        if len(message) > MAX_MESSAGE_LENGTH:
            return chat_failure("Please keep each message under 2,000 characters.")
        if language not in SUPPORTED_LANGUAGES:
            return chat_failure("Choose one of the supported chat languages.")
        preferences = self.chat.merge_preferences(extract_travel_preferences(message))
        try:
            flights = search_real_flights(preferences)
            inventory_available = True
        except Exception:
            logger.exception("Unable to search ARMS flight inventory for chat request")
            flights, inventory_available = [], False
        try:
            response = get_travel_response(
                message,
                flights,
                language=language,
                session_context=self.chat.history,
                api_key=self.request.POST.get("api_key") or self.chat.api_key,
                ai_provider=self.request.POST.get("provider") or self.chat.provider,
                ai_model=self.request.POST.get("model") or self.chat.model,
                travel_preferences=preferences,
            )
        except Exception:
            logger.exception("Travel assistant response failed")
            response = RESPONSE_UNAVAILABLE
        if not inventory_available:
            response += INVENTORY_UNAVAILABLE_NOTE
        self.chat.remember_exchange(message, response)
        return JsonResponse(
            {
                "status": "success",
                "response": response,
                "preferences": preferences,
                "flights": flights,
                "flight_count": len(flights),
                "inventory_available": inventory_available,
            }
        )

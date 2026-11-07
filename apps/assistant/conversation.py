from .preferences import merge_with_previous, storable
from .text import contains_guest_reference

HISTORY_LIMIT = 10
USER_CONTENT_LIMIT = 300
ASSISTANT_CONTENT_LIMIT = 600


class ChatSession:
    history_key = "ai_chat_history"
    preferences_key = "ai_travel_preferences"
    api_key_key = "ai_api_key"
    provider_key = "ai_provider"
    model_key = "ai_model"

    def __init__(self, session):
        self.session = session

    @property
    def api_key(self):
        return self.session.get(self.api_key_key)

    @property
    def provider(self):
        return self.session.get(self.provider_key, "auto")

    @property
    def model(self):
        return self.session.get(self.model_key)

    @property
    def history(self):
        history = self.session.get(self.history_key, [])
        return history if isinstance(history, list) else []

    def save_settings(self, api_key, provider, model, clear_key):
        if clear_key:
            self.session.pop(self.api_key_key, None)
        elif api_key:
            self.session[self.api_key_key] = api_key
        self.session[self.provider_key] = provider
        self.session[self.model_key] = model

    def clear_conversation(self):
        self.session.pop(self.history_key, None)
        self.session.pop(self.preferences_key, None)

    def merge_preferences(self, current):
        merged = merge_with_previous(current, self.session.get(self.preferences_key))
        self.session[self.preferences_key] = storable(merged)
        return merged

    def remember_exchange(self, message, response):
        if contains_guest_reference(message):
            return
        history = [
            *self.history,
            {"role": "user", "content": message[:USER_CONTENT_LIMIT]},
            {"role": "assistant", "content": response[:ASSISTANT_CONTENT_LIMIT]},
        ]
        self.session[self.history_key] = history[-HISTORY_LIMIT:]

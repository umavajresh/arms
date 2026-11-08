from django.core.management.base import BaseCommand, CommandError

from apps.assistant.llm import ChatCompletionClient, ProviderConfiguration

TEST_PROMPT = [
    {
        "role": "user",
        "content": "Reply with one short sentence confirming you can help travellers.",
    }
]


class Command(BaseCommand):
    help = "Send a short test message to the configured AI provider."

    def handle(self, *args, **options):
        configuration = ProviderConfiguration.from_settings()
        if not configuration.is_configured:
            raise CommandError(
                "No AI provider key is configured. Set OPENROUTER_API_KEY."
            )
        self.stdout.write(
            "Provider: %s, model: %s" % (configuration.provider, configuration.model)
        )
        reply = ChatCompletionClient(configuration).complete(TEST_PROMPT)
        if reply is None:
            raise CommandError(
                "The provider did not return a usable reply. "
                "The warnings above give the reason."
            )
        self.stdout.write(self.style.SUCCESS("Reply: %s" % reply[:200]))

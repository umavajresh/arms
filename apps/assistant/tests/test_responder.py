from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.assistant.llm import get_llm_provider_status
from apps.assistant.preferences import extract_travel_preferences
from apps.assistant.pricing import compute_price_breakdown
from apps.assistant.prompts import build_grounding_context
from apps.assistant.recommendations import build_local_recommendations
from apps.assistant.responder import get_travel_response

NO_PROVIDER_KEYS = {
    "openrouter": "",
    "groq": "",
    "huggingface": "",
    "openai": "",
}


class PreferenceExtractionTests(SimpleTestCase):
    def test_budget_duration_and_origin(self):
        preferences = extract_travel_preferences(
            "I have a budget of ₹15,000 for 3 days from Chennai"
        )
        self.assertEqual(preferences["budget"], 15000)
        self.assertEqual(preferences["days"], 3)
        self.assertEqual(preferences["origin"], "Chennai")

    def test_destination_season_and_style(self):
        preferences = extract_travel_preferences(
            "Plan an international food and culture trip from Chennai to Bangkok "
            "in December"
        )
        self.assertEqual(preferences["origin"], "Chennai")
        self.assertEqual(preferences["destination"], "Bangkok")
        self.assertEqual(preferences["month"], "December")
        self.assertIn("food experiences", preferences["preferences"])
        self.assertIn("culture and heritage", preferences["preferences"])

    def test_overseas_destination_implies_international_trip(self):
        preferences = extract_travel_preferences(
            "Plan a 4 day trip from Chennai to Bangkok"
        )
        self.assertEqual(preferences["trip_type"], "international")
        self.assertEqual(preferences["destination"], "Bangkok")

    def test_kadapa_under_twelve_thousand(self):
        preferences = extract_travel_preferences("plan a trip to Kadapa under₹12000")
        self.assertEqual(preferences["destination"], "Kadapa")
        self.assertEqual(preferences["budget"], 12000)
        self.assertEqual(preferences["trip_type"], "domestic")

    def test_alias_is_resolved_to_catalog_name(self):
        preferences = extract_travel_preferences("Any ideas for bengaluru food?")
        self.assertEqual(preferences["destination"], "Bangalore")


class PricingTests(SimpleTestCase):
    def test_economy_breakdown_components(self):
        breakdown = compute_price_breakdown(10000.0)
        self.assertEqual(breakdown["base_fare"], 6800.0)
        self.assertEqual(breakdown["fuel_surcharge"], 1400.0)
        self.assertEqual(breakdown["airport_fee"], 1000.0)
        self.assertEqual(breakdown["gst"], 800.0)
        self.assertEqual(breakdown["total"], 10000.0)
        self.assertEqual(breakdown["base_pct"], 68)


@override_settings(
    ARMS_AI_PROVIDER_API_KEYS=NO_PROVIDER_KEYS, ARMS_AI_FALLBACK_API_KEY=""
)
class LocalResponseTests(TestCase):
    def test_budget_prompt_returns_recommendations(self):
        response = get_travel_response("My budget is ₹12,000 for 3 days")
        self.assertIn("₹", response)
        self.assertIn("Budget", response)

    def test_international_budget_recommends_overseas_destinations(self):
        response = get_travel_response(
            "My budget is ₹1,200,000 for 3 days. "
            "I want an international trip from Chennai."
        )
        self.assertIn("international", response.lower())
        self.assertTrue(
            any(
                city in response
                for city in (
                    "Dubai",
                    "Bangkok",
                    "Singapore",
                    "Bali",
                    "Paris",
                    "Colombo",
                )
            )
        )
        personalized = get_travel_response(
            "International food and culture trip from Chennai in December, "
            "budget ₹1,200,000"
        )
        self.assertIn("Sample seasonal note for December", personalized)
        self.assertTrue(
            any(city in personalized for city in ("Bangkok", "Kuala Lumpur"))
        )

    def test_response_includes_supplied_flight_inventory(self):
        flight = {
            "code": "ARMS204",
            "from": "MAA - Chennai",
            "to": "BKK - Bangkok",
            "departure": "15 Dec 2026, 09:00 AM",
            "currency": "INR",
            "economy_price": 24000,
            "economy_available": 12,
        }
        response = get_travel_response(
            "International trip from Chennai to Bangkok for 3 days in December",
            [flight],
        )
        self.assertIn("ARMS204", response)
        self.assertIn("INR 24000", response)
        self.assertIn("planning estimates, not booking quotes", response)

    def test_policy_questions_point_to_carrier_sources(self):
        baggage = get_travel_response("What is the baggage allowance?")
        self.assertIn("authoritative baggage-policy source", baggage)
        self.assertNotIn("7 kg", baggage)
        cancellation = get_travel_response("How can I cancel my booking?")
        self.assertIn("This only updates the ARMS record", cancellation)
        self.assertIn("My Bookings", cancellation)
        check_in = get_travel_response("What are the airport check-in times?")
        self.assertIn(
            "does not have an authoritative check-in or boarding-time source", check_in
        )

    def test_spanish_baggage_answer(self):
        response = get_travel_response(
            "¿Cuál es la política de equipaje?", language="es"
        )
        self.assertIn("fuente oficial de equipaje", response)

    def test_kadapa_plan_matches_destination_and_budget(self):
        response = get_travel_response("plan a trip to Kadapa under₹12000")
        self.assertIn("Kadapa", response)
        self.assertIn("within the supplied budget", response)
        self.assertIn("Gandikota", response)
        self.assertIn("Belum Caves", response)
        self.assertNotIn("Singapore", response)

    def test_price_chart_without_code_asks_for_one(self):
        response = get_travel_response("show fare breakdown price chart")
        self.assertIn("provide a flight code", response)

    def test_price_chart_for_unknown_flight_does_not_substitute(self):
        response = get_travel_response("price chart for flight ZX999")
        self.assertIn("No matching flight fare is recorded", response)

    def test_unknown_destination_gets_no_synthetic_prices(self):
        self.assertEqual(
            build_local_recommendations(
                {"destination": "Atlantis", "trip_type": "international", "days": 3}
            ),
            [],
        )
        response = get_travel_response("Plan a trip to Atlantis")
        self.assertIn("do not have a verified destination guide", response)
        self.assertNotIn("nearest hub", response.lower())

    def test_greeting_does_not_default_to_a_destination(self):
        response = get_travel_response("Hello")
        self.assertIn("Welcome to", response)
        self.assertNotIn("Suggested Goa itinerary", response)

    def test_destination_guides(self):
        self.assertIn("Shibuya", get_travel_response("Tell me about Tokyo"))
        self.assertIn("Eiffel Tower", get_travel_response("Trip to Paris"))

    def test_booking_reference_is_routed_to_verified_portal(self):
        with patch("apps.assistant.responder.call_external_llm") as model_call:
            response = get_travel_response(
                "Please look up GUEST-AB12-CD34",
                api_key="sk-or-test-key",
                ai_provider="openrouter",
            )
        self.assertIn("Guest Booking Lookup", response)
        model_call.assert_not_called()


class ModelResponseTests(TestCase):
    def test_model_receives_history_and_requested_language(self):
        with (
            patch(
                "apps.assistant.responder.build_grounding_context",
                return_value="Verified baggage policy facts.",
            ),
            patch(
                "apps.assistant.responder.call_external_llm",
                return_value="Réponse personnalisée.",
            ) as model_call,
        ):
            response = get_travel_response(
                "What is the baggage allowance?",
                language="fr",
                session_context=[
                    {"role": "user", "content": "I am planning a trip to Paris."},
                    {"role": "assistant", "content": "How long will you stay?"},
                ],
                api_key="test-provider-key",
                ai_provider="openrouter",
            )
        self.assertEqual(response, "Réponse personnalisée.")
        messages = model_call.call_args.kwargs["messages"]
        self.assertIn("Respond in French", messages[0]["content"])
        self.assertEqual(messages[1]["content"], "I am planning a trip to Paris.")
        self.assertEqual(messages[-1]["content"], "What is the baggage allowance?")

    def test_empty_search_does_not_add_unfiltered_inventory(self):
        with patch("apps.assistant.prompts.bookable_flights") as inventory:
            context = build_grounding_context([])
        inventory.assert_not_called()
        self.assertIn("No matching scheduled flights", context)


class ProviderConfigurationTests(SimpleTestCase):
    @override_settings(
        ARMS_AI_PROVIDER_API_KEYS={**NO_PROVIDER_KEYS, "openrouter": "sk-or-test-key"},
        ARMS_AI_FALLBACK_API_KEY="",
    )
    def test_auto_provider_uses_configured_key(self):
        self.assertEqual(
            get_llm_provider_status(provider="auto"),
            {"has_key": True, "provider": "openrouter", "source": "environment"},
        )

    @override_settings(
        ARMS_AI_PROVIDER_API_KEYS=NO_PROVIDER_KEYS, ARMS_AI_FALLBACK_API_KEY="gsk_x"
    )
    def test_fallback_key_provider_is_inferred_from_prefix(self):
        self.assertEqual(get_llm_provider_status()["provider"], "groq")

    def test_session_key_takes_precedence(self):
        status = get_llm_provider_status(api_key="hf_session", provider="auto")
        self.assertEqual(status["provider"], "huggingface")
        self.assertEqual(status["source"], "session")

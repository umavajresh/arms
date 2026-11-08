import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.assistant.inventory import search_real_flights
from apps.assistant.llm import call_external_llm
from apps.assistant.preferences import extract_travel_preferences
from apps.assistant.tools import execute_travel_tool
from apps.assistant.views import chat_limiter
from apps.bookings.tests.factories import make_reservation
from apps.flights.tests.factories import (
    make_aircraft,
    make_airline,
    make_airport,
    make_flight,
)

NO_KEYS = {"openrouter": "", "groq": "", "huggingface": "", "openai": ""}
OPENROUTER_ONLY = {**NO_KEYS, "openrouter": "sk-or-test-key"}


def provider_response(status_code, payload):
    response = Mock(status_code=status_code)
    response.json.return_value = payload
    return response


class TravelToolTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flight = make_flight(
            code="SK101",
            airline=make_airline(name="Skyline Air"),
            origin=make_airport("MAA", name="Chennai"),
            destination=make_airport("DXB", name="Dubai", country="UAE"),
            aircraft=make_aircraft(
                code="AC99", business_capacity=2, economy_capacity=5
            ),
            departs_in=timedelta(days=1),
            business_class_price=600,
            economy_price=250,
        )

    def test_search_flights(self):
        result = execute_travel_tool(
            "search_flights", {"origin": "Chennai", "destination": "Dubai"}
        )
        self.assertEqual([flight["code"] for flight in result], ["SK101"])
        self.assertEqual(result[0]["available_seats"], 5)

    def test_flight_details(self):
        result = execute_travel_tool("get_flight_details", {"code": "SK101"})
        self.assertEqual(result["code"], "SK101")
        self.assertEqual(result["airline"], "Skyline Air")

    def test_price_chart(self):
        result = execute_travel_tool("get_price_chart", {"code": "sk101"})
        self.assertEqual(result["economy"]["total"], 250.0)

    def test_reservation_lookup_requires_both_verifiers(self):
        reservation = make_reservation(
            self.flight, first_name="Alex", last_name="Morgan", email="alex@example.com"
        )
        missing = execute_travel_tool(
            "lookup_reservation",
            {"reference": reservation.booking_reference, "email": "alex@example.com"},
        )
        verified = execute_travel_tool(
            "lookup_reservation",
            {
                "reference": reservation.booking_reference,
                "email": "alex@example.com",
                "last_name": "Morgan",
            },
        )
        self.assertIn("error", missing)
        self.assertEqual(verified["reference"], reservation.booking_reference)

    def test_invalid_arguments_are_rejected(self):
        self.assertIn("error", execute_travel_tool("search_flights", []))
        self.assertIn(
            "positive finite number",
            execute_travel_tool("search_flights", {"max_price": float("nan")})["error"],
        )
        self.assertIn(
            "unsupported fields",
            execute_travel_tool(
                "search_flights", {"origin": "Chennai", "delete_all": True}
            )["error"],
        )
        self.assertEqual(
            execute_travel_tool("drop_tables", {}),
            {"error": "Unsupported travel tool."},
        )

    @override_settings(ARMS_AI_PROVIDER_API_KEYS=OPENROUTER_ONLY, ARMS_AI_MODEL="")
    def test_model_tool_call_is_executed_and_followed_by_grounded_completion(self):
        tool_response = Mock(status_code=200)
        tool_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_flights_1",
                                "type": "function",
                                "function": {
                                    "name": "search_flights",
                                    "arguments": json.dumps(
                                        {"origin": "Chennai", "destination": "Dubai"}
                                    ),
                                },
                            }
                        ],
                    }
                }
            ]
        }
        final_response = Mock(status_code=200)
        final_response.json.return_value = {
            "choices": [{"message": {"content": "ARMS lists flight SK101."}}]
        }
        with patch(
            "apps.assistant.llm.requests.post",
            side_effect=[tool_response, final_response],
        ) as request:
            result = call_external_llm(
                [{"role": "user", "content": "Find a flight from Chennai to Dubai."}]
            )
        self.assertEqual(result, "ARMS lists flight SK101.")
        first_payload = request.call_args_list[0].kwargs["json"]
        self.assertEqual(
            {tool["function"]["name"] for tool in first_payload["tools"]},
            {"search_flights", "get_flight_details", "get_price_chart"},
        )
        final_messages = request.call_args_list[1].kwargs["json"]["messages"]
        self.assertTrue(
            any(
                message.get("role") == "tool" and "SK101" in message["content"]
                for message in final_messages
            )
        )
        self.assertNotIn("tools", request.call_args_list[1].kwargs["json"])

    @override_settings(ARMS_AI_PROVIDER_API_KEYS=OPENROUTER_ONLY, ARMS_AI_MODEL="")
    def test_request_is_retried_without_tools_when_the_model_rejects_them(self):
        rejected = provider_response(404, {"error": {"message": "No tool support"}})
        answered = provider_response(
            200, {"choices": [{"message": {"content": "Here is a plan."}}]}
        )
        with patch(
            "apps.assistant.llm.requests.post", side_effect=[rejected, answered]
        ) as request:
            result = call_external_llm([{"role": "user", "content": "Plan a trip"}])
        self.assertEqual(result, "Here is a plan.")
        self.assertIn("tools", request.call_args_list[0].kwargs["json"])
        self.assertNotIn("tools", request.call_args_list[1].kwargs["json"])

    @override_settings(ARMS_AI_PROVIDER_API_KEYS=OPENROUTER_ONLY, ARMS_AI_MODEL="")
    def test_empty_reply_is_retried_once(self):
        empty = provider_response(200, {"choices": [{"message": {"content": ""}}]})
        answered = provider_response(
            200, {"choices": [{"message": {"content": "Second try."}}]}
        )
        with patch("apps.assistant.llm.requests.post", side_effect=[empty, answered]):
            self.assertEqual(
                call_external_llm([{"role": "user", "content": "x"}]), "Second try."
            )
        with patch("apps.assistant.llm.requests.post", return_value=empty) as post:
            self.assertIsNone(call_external_llm([{"role": "user", "content": "x"}]))
        self.assertEqual(post.call_count, 2)

    @override_settings(ARMS_AI_PROVIDER_API_KEYS=OPENROUTER_ONLY, ARMS_AI_MODEL="")
    def test_tool_markup_written_as_text_is_never_shown(self):
        leaked = provider_response(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": '<dots_function_call><invoke name="x">'
                            "</invoke></dots_function_call>"
                        }
                    }
                ]
            },
        )
        answered = provider_response(
            200, {"choices": [{"message": {"content": "Clean answer."}}]}
        )
        with patch("apps.assistant.llm.requests.post", side_effect=[leaked, answered]):
            self.assertEqual(
                call_external_llm([{"role": "user", "content": "x"}]), "Clean answer."
            )

    def test_flight_search_tool_matches_city_names(self):
        paris = make_airport(
            "CDG", name="Charles de Gaulle Airport", city="Paris", country="France"
        )
        delhi = make_airport("DEL", name="Indira Gandhi International", city="Delhi")
        make_flight(
            code="PAR1",
            airline=make_airline(code="PRT", name="Paris Test Air"),
            origin=delhi,
            destination=paris,
        )
        result = execute_travel_tool(
            "search_flights", {"origin": "Delhi", "destination": "Paris"}
        )
        self.assertEqual([flight["code"] for flight in result], ["PAR1"])

    @override_settings(ARMS_AI_PROVIDER_API_KEYS=OPENROUTER_ONLY, ARMS_AI_MODEL="")
    def test_rate_limited_request_is_not_retried(self):
        limited = provider_response(429, {"error": {"message": "Rate limit"}})
        with patch("apps.assistant.llm.requests.post", return_value=limited) as post:
            self.assertIsNone(call_external_llm([{"role": "user", "content": "x"}]))
        post.assert_called_once()

    @override_settings(
        ARMS_AI_PROVIDER_API_KEYS=OPENROUTER_ONLY, ARMS_AI_MODEL="vendor/chosen-model"
    )
    def test_configured_model_and_attribution_headers_are_sent(self):
        answered = provider_response(
            200, {"choices": [{"message": {"content": "Ready."}}]}
        )
        with patch("apps.assistant.llm.requests.post", return_value=answered) as post:
            call_external_llm([{"role": "user", "content": "x"}])
        self.assertEqual(post.call_args.kwargs["json"]["model"], "vendor/chosen-model")
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"], "Bearer sk-or-test-key"
        )
        self.assertEqual(
            post.call_args.kwargs["headers"]["X-Title"], "ARMS Travel Assistant"
        )

    @override_settings(ARMS_AI_PROVIDER_API_KEYS=OPENROUTER_ONLY, ARMS_AI_MODEL="")
    def test_model_requesting_unknown_tool_is_refused(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "lookup_reservation",
                                    "arguments": "{}",
                                },
                            }
                        ]
                    }
                }
            ]
        }
        with patch("apps.assistant.llm.requests.post", return_value=response):
            self.assertIsNone(call_external_llm([{"role": "user", "content": "x"}]))


class InventorySearchTests(TestCase):
    def test_international_search_matches_origin_and_excludes_domestic_routes(self):
        airline = make_airline()
        chennai = make_airport("MAA", name="Chennai International", city="Chennai")
        bangkok = make_airport(
            "BKK", name="Suvarnabhumi", city="Bangkok", country="Thailand"
        )
        goa = make_airport("GOI", name="Goa International", city="Goa")
        for code, destination in (("INT204", bangkok), ("DOM101", goa)):
            make_flight(
                code=code,
                airline=airline,
                origin=chennai,
                destination=destination,
                departs_in=timedelta(days=10),
                economy_price=24000,
            )
        matches = search_real_flights(
            extract_travel_preferences("International trip from Chennai")
        )
        self.assertEqual([flight["code"] for flight in matches], ["INT204"])
        self.assertEqual(matches[0]["currency"], "INR")
        self.assertEqual(matches[0]["economy_price"], 24000.0)


class ChatApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def post(self, **data):
        return self.client.post(reverse("assistant:chat-api"), data)

    def test_chat_page_renders(self):
        self.assertContains(self.client.get(reverse("assistant:chat")), "AI")

    def test_trip_preferences_carry_into_follow_up_turns(self):
        with (
            patch("apps.assistant.views.search_real_flights", return_value=[]),
            patch(
                "apps.assistant.views.get_travel_response",
                return_value="Travel response",
            ) as responder,
        ):
            first = self.post(message="Plan a 3-day trip to Tokyo under INR 50000")
            follow_up = self.post(message="Make it more cultural")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(follow_up.status_code, 200)
        carried = responder.call_args.kwargs["travel_preferences"]
        self.assertEqual(carried["destination"], "Tokyo")
        self.assertEqual(carried["budget"], 50000)
        self.assertEqual(carried["days"], 3)
        self.assertEqual(len(self.client.session["ai_chat_history"]), 4)

    def test_clear_chat_removes_session_memory(self):
        session = self.client.session
        session["ai_chat_history"] = [{"role": "user", "content": "Plan a trip"}]
        session["ai_travel_preferences"] = {"destination": "Tokyo"}
        session.save()
        self.assertEqual(self.post(action="clear_chat").status_code, 200)
        self.assertNotIn("ai_chat_history", self.client.session)
        self.assertNotIn("ai_travel_preferences", self.client.session)

    def test_message_validation(self):
        self.assertEqual(self.post(message="").status_code, 400)
        self.assertEqual(self.post(message="x" * 2001).status_code, 400)
        self.assertEqual(self.post(message="hi", language="xx").status_code, 400)

    @override_settings(ARMS_AI_PROVIDER_API_KEYS=NO_KEYS, ARMS_AI_FALLBACK_API_KEY="")
    def test_keys_and_models_sent_by_the_browser_are_ignored(self):
        with patch("apps.assistant.responder.call_external_llm") as model_call:
            response = self.post(
                message="Plan a trip to Goa",
                api_key="sk-or-v1-visitor-key",
                provider="openrouter",
                model="any/model",
            )
        self.assertEqual(response.status_code, 200)
        model_call.assert_not_called()

    def test_chat_page_offers_no_key_or_model_settings(self):
        page = self.client.get(reverse("assistant:chat"))
        self.assertNotContains(page, "aiSettingsModal")
        self.assertNotContains(page, "API Key")

    def test_direct_tool_calls_validate_input(self):
        self.assertEqual(
            self.post(tool_name="search_flights", tool_args="not-json").status_code, 400
        )
        response = self.post(tool_name="search_flights", tool_args="{}")
        self.assertEqual(response.json()["tool_result"], [])

    def test_rate_limit_allows_thirty_requests_and_rejects_the_next(self):
        request = RequestFactory().post("/assistant/api/")
        request.META["REMOTE_ADDR"] = "192.0.2.10"
        results = [chat_limiter.is_limited(request) for _ in range(31)]
        self.assertEqual(results[:30], [False] * 30)
        self.assertIs(results[30], True)

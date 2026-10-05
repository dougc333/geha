"""Query API (query/lambda_function.py, app.py, chat.py) with no AWS or database.

Requests that would reach Bedrock or Postgres are either stopped earlier (access
key, validation) or run against stubs.
"""

import json
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from support import load

lambda_function = load("lambda_function", "query/lambda_function.py")
import chat  # noqa: E402  (query/ is on sys.path via support)
import signup.router as signup_router  # noqa: E402

KEY = {"X-API-Key": "test-key"}


class AccessKeyTest(unittest.TestCase):
    client = TestClient(lambda_function.app)

    def test_health_needs_no_key(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})

    def test_api_rejects_missing_or_wrong_key(self):
        self.assertEqual(self.client.get("/api/documents").status_code, 401)
        self.assertEqual(self.client.get("/api/documents", headers={"X-API-Key": "nope"}).status_code, 401)

    def test_cors_preflight_needs_no_key(self):
        response = self.client.options("/api/chat", headers={
            "Origin": "https://example.com", "Access-Control-Request-Method": "POST"})
        self.assertEqual(response.status_code, 200)

    def test_pages_need_no_key_and_are_not_cached(self):
        for path in ("/", "/chat", "/backends", "/signup"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("text/html", response.headers["content-type"])
            self.assertEqual(response.headers["cache-control"], "no-cache")

    def test_chat_route_reaches_chat_handler(self):
        # A helper once ended up under @router.post("/api/chat") and every chat
        # request failed validation. The handler's own check proves the route.
        response = self.client.post("/api/chat", headers=KEY, json={
            "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "The last message must be from the user")


class HistoryTest(unittest.TestCase):
    def test_long_earlier_answer_is_trimmed_not_rejected(self):
        # A library answer listing all 203 titles came back as history and got a 422.
        message = chat.ChatMessage(role="assistant", content="x" * 12000)
        self.assertEqual(len(message.content), chat.MAX_MESSAGE_CHARS)

    def test_long_user_message_is_still_rejected(self):
        with self.assertRaises(ValueError):
            chat.ChatMessage(role="user", content="x" * 12000)


class SignupApiTest(unittest.TestCase):
    client = TestClient(lambda_function.app)
    application_id = "11111111-1111-1111-1111-111111111111"

    def application(self, version=0):
        return {
            "id": self.application_id,
            "member_ref": "local-demo-member",
            "product": "dental",
            "coverage_year": 2026,
            "stage": "eligibility",
            "status": "active",
            "slots": {},
            "version": version,
        }

    def test_create_signup_session(self):
        database = mock.MagicMock()
        database.return_value.__enter__.return_value = object()
        with (
            mock.patch.object(signup_router, "database", database),
            mock.patch.object(
                signup_router.repository,
                "create_application",
                return_value=self.application(),
            ),
        ):
            response = self.client.post(
                "/api/signup/sessions",
                headers=KEY,
                json={"product": "dental", "coverage_year": 2026},
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["application"]["stage"], "eligibility")
        self.assertIn("FEDVIP", response.json()["reply"])

    def test_stale_signup_message_returns_conflict_before_rag(self):
        with mock.patch.object(signup_router, "_load", return_value=self.application(version=2)):
            response = self.client.post(
                f"/api/signup/{self.application_id}/messages",
                headers=KEY,
                json={
                    "client_message_id": "22222222-2222-2222-2222-222222222222",
                    "message": "yes",
                    "expected_version": 1,
                },
            )
        self.assertEqual(response.status_code, 409)


class RouterTest(unittest.TestCase):
    def route(self, model_text: str, message: str = "tables in BERT") -> dict:
        with mock.patch.object(chat, "converse"), mock.patch.object(chat, "_text", return_value=model_text):
            return chat._route([chat.ChatMessage(role="user", content=message)])

    def test_unparseable_output_falls_back_to_content_search(self):
        decision = self.route("Sorry, I can't help with that.")
        self.assertEqual(decision["route"], "content")
        self.assertEqual(decision["search_query"], "tables in BERT")

    def test_json_inside_prose_and_year_cleanup(self):
        decision = self.route('Here: {"route": "list", "year_from": "2017", "year_to": "soon", '
                              '"search_query": ""} done')
        self.assertEqual(decision["route"], "list")
        self.assertEqual(decision["year_from"], 2017)
        self.assertIsNone(decision["year_to"])
        self.assertEqual(decision["search_query"], "tables in BERT")

    def test_unknown_route_becomes_content(self):
        self.assertEqual(self.route(json.dumps({"route": "delete"}))["route"], "content")


class FigureUrlsTest(unittest.TestCase):
    def connection(self, rows):
        connection = mock.MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchall.return_value = rows
        return connection

    def test_presigns_only_figure_chunks(self):
        s3 = mock.Mock()
        s3.generate_presigned_url.side_effect = lambda op, Params, ExpiresIn: f"https://signed/{Params['Key']}"
        connection = self.connection([(7, "figures/doc/p003_f01.png")])
        with mock.patch.object(chat, "CHUNK_BUCKET", "chunks-bucket"), mock.patch.object(chat, "s3", s3):
            urls = chat._figure_urls(connection, [5, 7])
        self.assertEqual(urls, {7: "https://signed/figures/doc/p003_f01.png"})
        s3.generate_presigned_url.assert_called_once_with(
            "get_object", Params={"Bucket": "chunks-bucket", "Key": "figures/doc/p003_f01.png"},
            ExpiresIn=chat.FIGURE_URL_SECONDS)

    def test_no_bucket_or_no_sources_skips_the_query(self):
        connection = self.connection([])
        with mock.patch.object(chat, "CHUNK_BUCKET", ""):
            self.assertEqual(chat._figure_urls(connection, [1]), {})
        with mock.patch.object(chat, "CHUNK_BUCKET", "chunks-bucket"):
            self.assertEqual(chat._figure_urls(connection, []), {})
        connection.cursor.assert_not_called()


if __name__ == "__main__":
    unittest.main()

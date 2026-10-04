"""Postgres persistence and optimistic concurrency for signup applications."""

from __future__ import annotations

import json
from typing import Any


class ApplicationNotFound(Exception):
    pass


class VersionConflict(Exception):
    pass


def _application(row) -> dict[str, Any]:
    if not row:
        raise ApplicationNotFound
    return {
        "id": row[0],
        "member_ref": row[1],
        "product": row[2],
        "coverage_year": row[3],
        "stage": row[4],
        "status": row[5],
        "slots": row[6] or {},
        "version": row[7],
    }


def create_application(
    connection, application_id: str, member_ref: str, product: str, coverage_year: int
) -> dict[str, Any]:
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO signup.applications
                       (id, member_ref, product, coverage_year, stage, status, slots)
                   VALUES (%s, %s, %s, %s, 'eligibility', 'active', '{}'::jsonb)
                   RETURNING id, member_ref, product, coverage_year, stage, status, slots, version""",
                (application_id, member_ref, product, coverage_year),
            )
            application = _application(cursor.fetchone())
            cursor.execute(
                """INSERT INTO signup.events
                       (application_id, event_type, from_version, to_version, payload)
                   VALUES (%s, 'created', 0, 0, %s::jsonb)""",
                (application_id, json.dumps({"product": product, "coverage_year": coverage_year})),
            )
            return application


def get_application(connection, application_id: str, member_ref: str) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, member_ref, product, coverage_year, stage, status, slots, version
               FROM signup.applications WHERE id = %s AND member_ref = %s""",
            (application_id, member_ref),
        )
        return _application(cursor.fetchone())


def get_idempotent_response(connection, application_id: str, client_message_id: str) -> dict | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT metadata->'response' FROM signup.messages
               WHERE application_id = %s AND client_message_id = %s AND role = 'assistant'""",
            (application_id, client_message_id),
        )
        row = cursor.fetchone()
        return row[0] if row else None


def document_ids_for_plan(
    connection, product: str, coverage_year: int, plan_code: str | None
) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT document_ids FROM signup.plan_versions
               WHERE product = %s AND coverage_year = %s
                 AND plan_code IN ('all', %s) AND active
               ORDER BY CASE WHEN plan_code = %s THEN 0 ELSE 1 END""",
            (product, coverage_year, plan_code or "all", plan_code or "all"),
        )
        return list(dict.fromkeys(doc for row in cursor.fetchall() for doc in (row[0] or [])))


def save_turn(
    connection,
    application: dict[str, Any],
    expected_version: int,
    client_message_id: str,
    user_message: str,
    response: dict[str, Any],
    event: str,
) -> dict[str, Any]:
    next_version = expected_version + 1
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE signup.applications
                   SET stage = %s, status = %s, slots = %s::jsonb,
                       version = version + 1, updated_at = now()
                   WHERE id = %s AND version = %s
                   RETURNING id, member_ref, product, coverage_year, stage, status, slots, version""",
                (
                    application["stage"],
                    application["status"],
                    json.dumps(application["slots"]),
                    application["id"],
                    expected_version,
                ),
            )
            updated = cursor.fetchone()
            if not updated:
                raise VersionConflict
            persisted = _application(updated)
            response = {**response, "application": persisted}
            cursor.execute(
                """INSERT INTO signup.messages
                       (application_id, client_message_id, role, content, metadata)
                   VALUES (%s, %s, 'user', %s, '{}'::jsonb),
                          (%s, %s, 'assistant', %s, jsonb_build_object('response', %s::jsonb))""",
                (
                    application["id"], client_message_id, user_message,
                    application["id"], client_message_id, response["reply"],
                    json.dumps(response, default=str),
                ),
            )
            cursor.execute(
                """INSERT INTO signup.events
                       (application_id, event_type, from_version, to_version, payload)
                   VALUES (%s, %s, %s, %s, %s::jsonb)""",
                (
                    application["id"], event, expected_version, next_version,
                    json.dumps({"stage": persisted["stage"], "status": persisted["status"]}),
                ),
            )
            return response

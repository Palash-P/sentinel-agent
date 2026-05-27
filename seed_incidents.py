"""Seed IncidentIQ with realistic incident logs through the public API."""
from __future__ import annotations

import argparse
import time
from typing import Final

import requests

TARGET_URL: Final[str] = "https://web-production-4435e.up.railway.app/api/analyze/"
TIMEOUT_SECONDS: Final[int] = 90


ERROR_LOGS: Final[list[str]] = [
    """django.db.utils.OperationalError: could not connect to server: Connection refused
    Is the server running on host "db.internal" (10.12.4.18) and accepting
    TCP/IP connections on port 5432?
        at django/db/backends/base/base.py:275 in ensure_connection
        at checkout/views.py:42 in create_order""",
    """redis.exceptions.ConnectionError: Error 111 connecting to redis:6379. Connection refused.
        at redis/connection.py:707 in connect
        at celery/backends/redis.py:215 in get
    Celery worker failed while reading task result for incident export job.""",
    """django.core.exceptions.DisallowedHost: Invalid HTTP_HOST header: 'web-production-4435e.up.railway.app'.
    You may need to add 'web-production-4435e.up.railway.app' to ALLOWED_HOSTS.
        at django/middleware/common.py:48 in process_request""",
    """psycopg2.errors.UndefinedTable: relation "incidents_incident" does not exist
    LINE 1: SELECT COUNT(*) AS "__count" FROM "incidents_incident"
        at django/db/backends/utils.py:105 in _execute
    Migration step was skipped during Railway release deploy.""",
    """ModuleNotFoundError: No module named 'google.genai'
        at incidents/gemini.py:16 in <module>
        at incidents/agent.py:14 in <module>
    Gunicorn worker failed to boot after dependency update.""",
    """pymongo.errors.ServerSelectionTimeoutError: SSL handshake failed: cluster0-shard-00-00.mongodb.net:27017
    Timeout: 30s, Topology Description: ReplicaSetNoPrimary
        at incidentiq/mongo.py:21 in get_client
        at incidents/models.py:57 in get_all_incidents""",
    """google.genai.errors.APIError: 429 RESOURCE_EXHAUSTED. Quota exceeded for quota metric
    'Generate Content API requests per minute' and limit 'Generate requests per minute'.
        at incidents/gemini.py:87 in generate_postmortem""",
    """django.core.files.storage.MissingFileError: The file 'staticfiles/manifest.json' could not be found
        at whitenoise/storage.py:166 in manifest_strict
    collectstatic did not run before Railway container startup.""",
    """gunicorn.errors.HaltServer: <HaltServer 'Worker failed to boot.' 3>
    django.core.exceptions.ImproperlyConfigured: Set the DJANGO_SECRET_KEY environment variable
        at django/conf/__init__.py:81 in _setup""",
    """psycopg2.OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections
        at django/db/backends/base/base.py:275 in ensure_connection
    API traffic spike exhausted PostgreSQL connection pool.""",
    """redis.exceptions.TimeoutError: Timeout reading from socket
        at redis/connection.py:538 in read_response
        at channels_redis/core.py:521 in receive
    Websocket notifications stalled during incident broadcast.""",
    """ValueError: Gemini returned non-JSON output.
        at incidents/gemini.py:105 in generate_postmortem
        at incidents/agent.py:78 in generate_postmortem
    Model response included markdown fences instead of strict JSON.""",
    """pymongo.errors.OperationFailure: PlanExecutor error during aggregation :: caused by ::
    Path 'embedding' needs to be indexed as knnVector, full error:
    {'ok': 0.0, 'code': 8, 'codeName': 'UnknownError'}
        at incidents/models.py:103 in find_similar_incidents""",
    """django.core.exceptions.ImproperlyConfigured: Error loading psycopg2 or psycopg module
    Did you install psycopg2-binary?
        at django/db/backends/postgresql/base.py:29 in <module>
    Railway build installed production requirements without PostgreSQL driver.""",
    """requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='api.github.com', port=443): Read timed out.
        at integrations/github.py:118 in fetch_recent_deployments
    Post-deploy health check blocked waiting on GitHub release metadata.""",
]


def post_error_log(index: int, error_log: str) -> bool:
    """Send one error log to the analyze endpoint and report whether it succeeded."""
    try:
        response = requests.post(
            TARGET_URL,
            json={"error_log": error_log},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[{index:02d}] failure: {exc}")
        return False

    try:
        payload = response.json()
    except requests.JSONDecodeError:
        print(f"[{index:02d}] failure: response was not JSON")
        return False

    title = str(payload.get("title", "untitled"))[:80]
    incident_id = payload.get("incident_id", "")
    print(f"[{index:02d}] success: {title} incident_id={incident_id}")
    return True


def parse_args() -> argparse.Namespace:
    """Parse optional incident indices to seed."""
    parser = argparse.ArgumentParser(description="Seed IncidentIQ incidents through the analyze API.")
    parser.add_argument(
        "--indices",
        nargs="*",
        type=int,
        help="One-based incident indices to seed; defaults to all incidents.",
    )
    return parser.parse_args()


def selected_logs(indices: list[int] | None) -> list[tuple[int, str]]:
    """Return selected one-based incident indices and logs."""
    if not indices:
        return list(enumerate(ERROR_LOGS, start=1))

    selected: list[tuple[int, str]] = []
    for index in indices:
        if index < 1 or index > len(ERROR_LOGS):
            print(f"[{index:02d}] failure: index is out of range")
            continue
        selected.append((index, ERROR_LOGS[index - 1]))
    return selected


def main() -> None:
    """Post selected seed logs and print a summary."""
    logs = selected_logs(parse_args().indices)
    successes = 0
    for position, (index, error_log) in enumerate(logs, start=1):
        if post_error_log(index, error_log):
            successes += 1
        if position < len(logs):
            time.sleep(3)
    failures = len(logs) - successes
    print(f"Finished seeding: {successes} succeeded, {failures} failed.")


if __name__ == "__main__":
    main()

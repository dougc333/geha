"""AWS Lambda entry point: the MCP server over stateless Streamable HTTP behind a Function URL.

The Function URL uses AuthType AWS_IAM, so only SigV4-signed requests from principals
granted lambda:InvokeFunctionUrl reach this code. MCP_ENV (one stack per tier) decides which
tools exist; audit records go to stdout, i.e. CloudWatch Logs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "mcp_benefits_server" / "src"))

from mangum import Mangum  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

from server import build_server  # noqa: E402

ENVIRONMENT = os.environ.get("MCP_ENV", "sandbox")
# DNS-rebinding protection guards servers on localhost or a private network from web pages
# in a victim's browser. This endpoint is public, IAM-authenticated, and its hostname isn't
# known until deployment (the SDK accepts exact hosts only), so the check is off here.
SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)


def _app():
    # Stateless mode: no session survives between requests, which suits Lambda. The SDK's
    # session manager can run only once per app, so each invocation gets a fresh app; the
    # parsed tables and indexes are module-level caches and are reused across warm invocations.
    return build_server(ENVIRONMENT, log_path=None,
                        log_level=os.environ.get("LOG_LEVEL", "WARNING")).streamable_http_app(
        stateless_http=True, json_response=True, transport_security=SECURITY)


def handler(event, context):
    return Mangum(_app(), lifespan="auto")(event, context)

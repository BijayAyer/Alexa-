# Friction Log

## 2026-10-18

- `uv sync --extra dev` initially failed because the package metadata referenced a missing `README.md`. Added the small README before retrying; the package then built and installed.
- The current MCP SDK docs describe v2, whose server API is no longer FastMCP. The v1 maintenance docs and installed `mcp 1.30.0` confirmed `FastMCP.run(transport="streamable-http")` and negotiation of protocol `2025-11-25`; pinned the dependency to `mcp<2` and verified the live handshake.
- The first Strands docs URLs returned 404 after the docs site moved. Resolved the canonical `/docs/user-guide/sdk/...` pages and checked the installed `MCPClient`, `OpenAIModel`, and `Agent` signatures before implementation.
- Strands 1.61.1 requires `boto3` and `botocore` at its core and its OpenAI extra installs `aws-bedrock-token-generator`. Excluding the AWS packages made top-level `import strands` fail because the package eagerly imports its Bedrock model. Restored the SDK's declared dependencies and disclosed that they are unused transitives; Cram makes no AWS calls.
- A local model returned several unrelated tool calls for one quiz request, and on a later request raised a Strands `APIError` after the MCP quiz tool had already succeeded. Restricting obvious requests to their matching tool and recovering a successful MCP result from Strands history prevents unrelated side effects and still returns the question.
- A short model-generated quiz contained fewer questions than requested. Added distinct note-based fallback questions to fill the requested count, with a regression test.
- Starlette's TestClient emitted a deprecation warning for its current `httpx` integration, but requests still passed. Kept the required `httpx` dependency and confirmed the runtime web routes and assets directly.
- A fresh HTTPS clone of the requested GitHub URL returned `Repository not found`, although authenticated pushes succeeded. Used a clean local clone of the committed repository for the final install/test check; no credential changes were made.
- Stopping the long-running MCP server while an Inspector-style SSE stream was closing printed `anyio.ClosedResourceError` from the SDK's standalone SSE writer. This occurred only during process shutdown; all health checks and MCP tool requests had already completed successfully.
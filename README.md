# Cram

Cram is a voice study assistant for Alexa+. A student saves notes, gets short spoken summaries, takes a quiz one question at a time, and asks what to review next. It is entered in the Alexa+ track of the Build, Ship, Shape: Amazon Developer Hackathon and the Open Source mini-challenge.

The complete default setup is free and local. No cloud account, paid service, or API key is needed. Alexa+ itself is simulated by the included web page; it is not a real Alexa+ add-on.

## How It Fits Together

```text
student's browser
	-> plain chat page on port 8080
	-> FastAPI and a Strands agent
	-> MCP tools over Streamable HTTP on port 8000
	-> SQLite file on this computer

The Strands agent also talks to an OpenAI-compatible model.
By default that is a local model served by LM Studio.
In a real Alexa+ setup, Alexa+ would replace the simulated web agent as the MCP client.
```

The MCP endpoint is `http://localhost:8000/mcp`. It uses the MCP `2025-11-25` protocol revision with Streamable HTTP. `/health` returns `{"status":"ok"}`.

## Run Locally

Install Python 3.12 and [uv](https://docs.astral.sh/uv/). From this folder:

```sh
uv sync --extra dev
cp .env.example .env
```

For model replies, start LM Studio, load a chat model with tool-calling support, and start its OpenAI-compatible server at `http://localhost:1234/v1`. Set `LOCAL_LLM_MODEL` in `.env` to the loaded model identifier. The MCP tools still have simple fallbacks if the model is absent, but the web simulator needs a working model for its Strands agent.

Use two terminals, starting the MCP server first:

```sh
uv run cram-server
```

```sh
uv run cram-web
```

Open [http://localhost:8080](http://localhost:8080). The server stores notes and quiz history in `cram.db` in the working directory by default.

To check the MCP tools interactively, run this in another terminal and connect the Inspector to `http://localhost:8000/mcp` using Streamable HTTP:

```sh
npx @modelcontextprotocol/inspector
```

## Settings

Copy `.env.example` to `.env`. All variables are optional for the local defaults.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `local` | `local` uses an OpenAI-compatible chat endpoint; `none` makes MCP tools use their fallbacks. |
| `LOCAL_LLM_URL` | `http://localhost:1234/v1` | Base URL for LM Studio or another OpenAI-compatible endpoint. |
| `LOCAL_LLM_MODEL` | `local-model` | Model identifier sent to the endpoint. Set this to the model loaded in LM Studio. |
| `LOCAL_LLM_API_KEY` | empty | Optional Bearer token for a compatible endpoint. Not needed for local LM Studio. |
| `MCP_URL` | `http://127.0.0.1:8000/mcp` | MCP endpoint used by the simulated Alexa+ agent. |
| `CRAM_DB_PATH` | `cram.db` | SQLite file path. |
| `CRAM_API_KEY` | empty | Optional Bearer token required on `/mcp`. The web app forwards it when set. `/health` stays public. |

You can point `LOCAL_LLM_URL` at an OpenAI-compatible endpoint that offers a free tier. Availability and free quotas are set by that provider; using one may require its own account or key. It is optional and is not needed for the free, local LM Studio setup.

## Alexa+ Integration

In a real Alexa+ add-on, Alexa+ is the MCP client and connects to Cram's Streamable HTTP endpoint. The seven tools and their plain-language descriptions are implemented on the MCP server, so Alexa+ can discover and call them. See the [Alexa+ MCP Toolkit overview](https://developer.amazon.com/docs/alexaplus/add-ons/mcp-toolkit-overview).

This project does not connect to an Alexa+ account or perform a real Alexa+ deployment. Its FastAPI page and Strands agent simulate that client so the MCP workflow can be tried locally.

## Tests

```sh
uv run pytest
```

Tests use SQLite temporary files and disable the LLM provider for deterministic fallback behavior.

## SDK Dependency Note

The Strands Agents SDK currently declares `boto3` and `botocore` as core dependencies. Its required OpenAI extra also installs `aws-bedrock-token-generator`. Strands imports its Bedrock model during package initialization, so excluding those packages makes `import strands` fail even though Cram never uses an AWS API. These packages are therefore present transitively, not called by Cram. This is a limitation of the required Strands dependency, not a Cram cloud integration.

## License

MIT. See [LICENSE](LICENSE).
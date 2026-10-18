# Free Deployment Options

## Local

The full project runs locally without an account. Follow the setup and two-terminal commands in [README.md](README.md).

## Local Network

The servers bind to `0.0.0.0`, so another device on the same trusted network can use `http://<computer-lan-address>:8080`. Keep the network private; the web app itself has no login.

## Cloudflare Quick Tunnel

For a temporary public MCP URL, install `cloudflared` and run:

```sh
cloudflared tunnel --url http://localhost:8000
```

The printed URL is temporary and changes when the tunnel stops. Set that URL plus `/mcp` as the MCP endpoint for the client. Set `CRAM_API_KEY` before starting Cram if the endpoint is public, and configure the client with the same Bearer token. The web simulator's `MCP_URL` can point to the tunnel URL too.

This quick tunnel is for demos, not a permanent deployment. No paid hosting or cloud account is required for the local project.
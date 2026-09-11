"""Runs the FastAPI app on an OS-assigned port and prints LISTENING_ON
<port> as soon as it is bound, the same contract the sibling
allocation-affirmation-workflow project's backend uses, so a test (or a
human) can start this process without ever assuming a fixed port is free
(BUILDER.md section 3a).
"""
import asyncio

import uvicorn

from app.api import app


async def main() -> None:
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    sock = config.bind_socket()
    port = sock.getsockname()[1]
    print(f"LISTENING_ON {port}", flush=True)
    await server.serve(sockets=[sock])


if __name__ == "__main__":
    asyncio.run(main())

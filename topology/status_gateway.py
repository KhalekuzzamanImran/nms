import asyncio
import json

from .current_state import read_status_payload, snapshot_path


async def status_websocket_application(scope, receive, send):
    if scope.get("path") != "/ws/status/":
        await send({"type": "websocket.close", "code": 4404})
        return

    while True:
        message = await receive()
        if message["type"] == "websocket.connect":
            await send({"type": "websocket.accept"})
            break
        if message["type"] == "websocket.disconnect":
            return

    last_mtime = None
    try:
        while True:
            message = await receive_with_timeout(receive, timeout=1.0)
            if message and message["type"] == "websocket.disconnect":
                return

            path = snapshot_path()
            if path.exists():
                mtime = path.stat().st_mtime
                if last_mtime != mtime:
                    payload = read_status_payload()
                    if payload:
                        await send(
                            {
                                "type": "websocket.send",
                                "text": json.dumps(payload),
                            }
                        )
                    last_mtime = mtime
    except asyncio.CancelledError:
        return


async def receive_with_timeout(receive, timeout: float):
    try:
        return await asyncio.wait_for(receive(), timeout=timeout)
    except asyncio.TimeoutError:
        return None

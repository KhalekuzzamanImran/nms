import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import parse_qs

import paramiko
from django.core import signing


SESSION_TTL_SECONDS = 300


@dataclass
class PendingSession:
    token: str
    device: str
    host: str
    port: int
    username: str
    password: str
    created_at: float


class SshRuntimeSession:
    def __init__(self, session: PendingSession):
        self.session = session
        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None
        self.closed = False

    async def start(self) -> None:
        await asyncio.to_thread(self._connect)

    def _connect(self) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.session.host,
            port=self.session.port,
            username=self.session.username,
            password=self.session.password,
            timeout=8,
            banner_timeout=8,
            auth_timeout=8,
            look_for_keys=False,
            allow_agent=False,
        )
        channel = client.invoke_shell(width=120, height=32)
        channel.settimeout(0.0)
        self.client = client
        self.channel = channel

    async def write(self, data: str) -> None:
        if not self.channel or self.closed:
            return
        await asyncio.to_thread(self.channel.send, data)

    async def read(self) -> bytes:
        if not self.channel or self.closed:
            return b""
        if not self.channel.recv_ready():
            return b""
        return await asyncio.to_thread(self.channel.recv, 4096)

    async def exit_status_ready(self) -> bool:
        if not self.channel:
            return True
        return await asyncio.to_thread(self.channel.closed.__bool__)

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.channel:
            await asyncio.to_thread(self.channel.close)
            self.channel = None
        if self.client:
            await asyncio.to_thread(self.client.close)
            self.client = None


class SshSessionManager:
    def __init__(self) -> None:
        self.signer = signing.TimestampSigner()
        self.pending_sessions: Dict[str, PendingSession] = {}

    def _purge_expired(self) -> None:
        cutoff = time.time() - SESSION_TTL_SECONDS
        expired_tokens = [
            token
            for token, session in self.pending_sessions.items()
            if session.created_at < cutoff
        ]
        for token in expired_tokens:
            self.pending_sessions.pop(token, None)

    def create_pending_session(
        self,
        *,
        device: str,
        host: str,
        port: int,
        username: str,
        password: str,
    ) -> str:
        self._purge_expired()
        token = self.signer.sign(uuid.uuid4().hex)
        self.pending_sessions[token] = PendingSession(
            token=token,
            device=device,
            host=host,
            port=port,
            username=username,
            password=password,
            created_at=time.time(),
        )
        return token

    def consume(self, token: str) -> Optional[PendingSession]:
        self._purge_expired()
        try:
            self.signer.unsign(token, max_age=SESSION_TTL_SECONDS)
        except signing.BadSignature:
            return None
        return self.pending_sessions.pop(token, None)


session_manager = SshSessionManager()


async def ssh_websocket_application(scope, receive, send):
    if scope["type"] != "websocket" or scope.get("path") != "/ws/ssh/":
        await send({"type": "websocket.close", "code": 1008})
        return

    query = parse_qs(scope.get("query_string", b"").decode())
    token = query.get("token", [None])[0]
    pending_session = session_manager.consume(token) if token else None

    await send({"type": "websocket.accept"})

    if not pending_session:
        await send({"type": "websocket.send", "text": "Invalid or expired SSH session.\r\n"})
        await send({"type": "websocket.close", "code": 4001})
        return

    runtime = SshRuntimeSession(pending_session)
    try:
        await runtime.start()
    except Exception as exc:
        await send({"type": "websocket.send", "text": f"Unable to start SSH: {exc}\r\n"})
        await send({"type": "websocket.close", "code": 1011})
        return

    async def stream_output():
        try:
            while True:
                chunk = await runtime.read()
                if chunk:
                    await send({
                        "type": "websocket.send",
                        "text": chunk.decode(errors="replace"),
                    })
                    continue

                if await runtime.exit_status_ready():
                    break

                await asyncio.sleep(0.05)
        finally:
            await runtime.close()
            await send({"type": "websocket.close", "code": 1000})

    reader_task = asyncio.create_task(stream_output())

    try:
        while True:
            message = await receive()
            message_type = message["type"]

            if message_type == "websocket.disconnect":
                break

            if message_type == "websocket.receive":
                text = message.get("text")
                if text:
                    await runtime.write(text)
    finally:
        reader_task.cancel()
        await runtime.close()

import asyncio
import json
import logging
import os
import urllib.request

from livekit.agents import JobContext, WorkerOptions, cli

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
MODEL = "qwen2.5:3b"
AVATAR_URL = os.environ.get("AVATAR_URL", "http://127.0.0.1:8010")

SYSTEM = (
    "你是企业AI视频客服小助手。用简体中文回答客户问题，"
    "语气友好专业，回答控制在三句话以内。"
)


def speak_via_avatar(text: str) -> str:
    """把 AI 答案交给 LiveTalking 驱动数字人口型（同机 HTTP，不经浏览器）。"""
    if not AVATAR_URL:
        return "avatar disabled"
    sess = _get_json(AVATAR_URL + "/api/admin/sessions")
    sessions = (sess.get("data") or {}).get("sessions") or []
    if not sessions:
        return "no avatar session"
    sid = sessions[-1]["sessionid"]
    _post_json(AVATAR_URL + "/human",
               {"sessionid": sid, "text": text[:160], "type": "echo"})
    return "avatar session=%s" % sid


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def ask_ollama(question: str) -> str:
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": question},
            ],
            "stream": False,
            "options": {"temperature": 0.3},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"]["content"].strip()


async def entrypoint(ctx: JobContext):
    logger = logging.getLogger("agent")
    await ctx.connect()
    room = ctx.room
    lp = room.local_participant

    async def on_ask(data):
        logger.info("RPC ask from %s: %s", data.caller_identity, data.payload)
        answer = await asyncio.to_thread(ask_ollama, data.payload)
        logger.info("answered: %s", answer[:80])
        try:
            await lp.send_text(f"[转写] {data.caller_identity} 问: {data.payload}\nAI 答: {answer}", topic="transcript")
        except Exception as e:
            logger.warning("send_text failed: %s", e)
        try:
            note = await asyncio.to_thread(speak_via_avatar, answer)
            logger.info("avatar: %s", note)
            await lp.send_text(f"[数字人] 已驱动口型播报（{note}）", topic="transcript")
        except Exception as e:
            logger.warning("avatar bridge unavailable: %s", e)
        return answer

    lp.register_rpc_method("ask", on_ask)
    try:
        await lp.set_name("AI客服")
    except Exception as e:  # noqa: BLE001
        logger.warning("set_name failed: %s", e)

    logger.info("agent ready in room=%s identity=%s", room.name, lp.identity)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="default",
        )
    )

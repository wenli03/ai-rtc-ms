import asyncio
import json
import logging
import urllib.request

from livekit.agents import JobContext, WorkerOptions, cli

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
MODEL = "qwen2.5:3b"

SYSTEM = (
    "你是企业AI视频客服小助手。用简体中文回答客户问题，"
    "语气友好专业，回答控制在三句话以内。"
)


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

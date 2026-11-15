

import json
import os
import re
from datetime import datetime, timezone
from itertools import count
from pathlib import Path
from uuid import uuid4
import gymnasium as gym
import browsergym.core  # registers "browsergym/openended"
from browsergym.core.action.highlevel import HighLevelActionSet
from browsergym.utils.obs import flatten_axtree_to_str
from openai import OpenAI

# Nous Portal (OpenAI-compatible)
client = OpenAI(
    api_key=os.environ["NOUS_API_KEY"],
    base_url="https://inference-api.nousresearch.com/v1",
)
MODEL = "Hermes-4-405B"   # or "Hermes-4-70B" for faster/cheaper

action_set = HighLevelActionSet(subsets=["chat", "bid", "nav"], strict=False, multiaction=False)

env = gym.make(
    "browsergym/openended",
    task_kwargs={"start_url": "https://www.google.com"},
    wait_for_user_message=True,
    action_mapping=action_set.to_python_code,
)
SYSTEM = f"""You are a web agent controlling a browser.
Each element in the accessibility tree has an id in brackets like [a51]; use it in actions.

Available actions:
{action_set.describe(with_long_description=False, with_examples=True)}

Think briefly, then output exactly ONE action inside <action></action> tags.
Example: <action>click('a51')</action>"""

history = []

run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
trajectory_dir = Path(__file__).resolve().parent / "trajectories"
trajectory_dir.mkdir(parents=True, exist_ok=True)
trajectory_path = trajectory_dir / f"{run_id}.jsonl"


def snapshot(observation: dict) -> dict:
    """Keep the text observations needed to replay and inspect an agent step."""
    return {
        "goal": observation.get("goal"),
        "chat_messages": observation.get("chat_messages"),
        "url": observation.get("url"),
        "last_action_error": observation.get("last_action_error"),
        "accessibility_tree": flatten_axtree_to_str(observation["axtree_object"]),
    }


def extract_action(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)  # strip Hermes reasoning
    m = re.search(r"<action>(.*?)</action>", text, flags=re.DOTALL)
    return m.group(1).strip() if m else text.strip().splitlines()[-1]

fd = os.open(trajectory_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as trajectory:
    def save(event: dict) -> None:
        trajectory.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        trajectory.flush()

    save({"event": "start", "schema_version": 1, "run_id": run_id,
          "model": MODEL, "system_prompt": SYSTEM})
    print("TRAJECTORY:", trajectory_path)
    current_step = 0
    current_action = None
    try:
        obs, info = env.reset()
        for step in count(1):
            current_step = step
            current_action = None
            before = snapshot(obs)
            chat = "\n".join(
                f"{m['role']}: {m['message']}" for m in before["chat_messages"]
            )
            user_prompt = f"""Conversation / goal:
{chat or before['goal']}

Current URL: {before['url']}
Previous actions: {history[-5:] or 'none'}
Last action error: {before['last_action_error'] or 'none'}

Accessibility tree:
{before['accessibility_tree']}"""

            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
            )
            raw = resp.choices[0].message.content
            action = extract_action(raw)
            current_action = action
            print("ACTION:", action)
            history.append(action)

            obs, reward, terminated, truncated, info = env.step(action)
            save({
                "event": "step",
                "run_id": run_id,
                "step": step,
                "observation": before,
                "user_prompt": user_prompt,
                "model_output": raw,
                "response_model": resp.model,
                "token_usage": resp.usage.model_dump() if resp.usage else None,
                "action": action,
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated,
                "env_info": info,
                "next_observation": snapshot(obs),
            })
            if terminated or truncated:
                save({"event": "end", "run_id": run_id, "steps": step,
                      "terminated": terminated, "truncated": truncated,
                      "final_reward": reward})
                break
    except Exception as exc:
        save({"event": "error", "run_id": run_id, "step": current_step,
              "action": current_action,
              "error_type": type(exc).__name__, "error": str(exc)})
        raise
    finally:
        env.close()

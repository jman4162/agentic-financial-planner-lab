"""Temporary CI diagnostic. Capture the writer prompt for a golden case and replay it against Ollama with CI settings.

Usage: python probe.py <repo> <case> <out_dir> [num_predict]
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

repo, case_name, out_dir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
num_predict = int(sys.argv[4]) if len(sys.argv) > 4 else 20000
sys.path.insert(0, str(repo / "src"))

import yaml  # noqa: E402
from rich.console import Console  # noqa: E402

import planner_lab.agents.memo_writer as mw  # noqa: E402
from planner_lab.agents.pipeline import run_analysis  # noqa: E402
from planner_lab.schemas.case_file import CaseFile  # noqa: E402

captured = {}


class Captured(Exception):
    pass


def fake(model, output_model, prompt, system_prompt):
    captured.update(prompt=prompt, system=system_prompt, schema=output_model.model_json_schema())
    raise Captured


mw.get_structured = fake
doc = yaml.safe_load((repo / "evals/golden" / f"{case_name}.yaml").read_text())
case = CaseFile.model_validate(doc["case"])
try:
    run_analysis(case, simulate=doc.get("simulate", False), confirm=lambda _: True,
                 console=Console(quiet=True))
except Captured:
    pass
except Exception as e:  # noqa: BLE001
    if not captured:
        raise
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / f"{case_name}.prompt.txt").write_text(captured["prompt"])

body = {
    "model": "qwen2.5:3b",
    "messages": [
        {"role": "system", "content": captured["system"]},
        {"role": "user", "content": captured["prompt"]},
    ],
    "format": captured["schema"],
    "stream": True,
    "options": {"num_ctx": 8192, "seed": 42, "temperature": 0, "num_predict": num_predict, **json.loads(__import__("os").environ.get("EXTRA_OPTS", "{}"))},
}
req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
start = time.monotonic()
text = []
final = {}
with urllib.request.urlopen(req, timeout=3600) as resp:
    for line in resp:
        chunk = json.loads(line)
        text.append(chunk.get("message", {}).get("content", ""))
        if len(text) % 500 == 0:
            print(f"{len(text)} chunks at {time.monotonic() - start:.0f}s: ...{''.join(text)[-160:]!r}", flush=True)
        if chunk.get("done"):
            final = chunk
out = "".join(text)
(out_dir / f"{case_name}.output.txt").write_text(out)
try:
    json.loads(out)
    valid = True
except ValueError:
    valid = False
print(json.dumps({
    "case": case_name,
    "seconds": round(time.monotonic() - start, 1),
    "prompt_eval_count": final.get("prompt_eval_count"),
    "eval_count": final.get("eval_count"),
    "done_reason": final.get("done_reason"),
    "output_chars": len(out),
    "valid_json": valid,
}))

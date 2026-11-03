"""Shared CodinGame API helpers and log parsing for local feedback loop."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

API_ROOT = "https://www.codingame.com/api/v1"
TOKEN_PATH = Path.home() / ".config/codingame/token"


def token() -> str:
    if not TOKEN_PATH.is_file():
        raise SystemExit(
            "Missing API token. Authenticate per CodinGame skill (~/.config/codingame/token)."
        )
    return TOKEN_PATH.read_text().strip()


def api(method: str, path: str, body: Optional[dict] = None, wait: Optional[int] = None) -> Any:
    url = f"{API_ROOT}{path}"
    if wait is not None:
        url += f"?wait={wait}" if "?" not in url else f"&wait={wait}"
    headers = {"Authorization": f"Bearer {token()}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise SystemExit(f"HTTP {e.code}: {raw[:500]}") from e
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def limits(challenge: str) -> dict:
    return api("GET", f"/limits?challenge={challenge}")


def test_game_running(challenge: str) -> Optional[int]:
    lim = limits(challenge)
    for w in lim.get("test_games", []):
        if w.get("remaining", 1) == 0 and w.get("used", 0) > 0:
            pass
    return None


CHALLENGE_IDE_URL = "https://www.codingame.com/ide/challenge/{public_id}"
CONTEST_URL = "https://www.codingame.com/contests/{public_id}"


@dataclass
class GameMetrics:
    opponent: str
    game_id: Optional[int]
    seed: Optional[int]
    game_options: Optional[str]
    win: bool
    my_score: int
    opp_score: int
    ranking: List[int]
    spawns: int
    captures: int
    move_errors: int
    timeout: bool
    eliminated: bool
    raw_scores: str

    def weakness_score(self) -> float:
        """Higher = worse game for us (for sorting weak spots)."""
        s = 0.0
        if not self.win:
            s += 1000
        if self.my_score == -1:
            s += 500
        if self.eliminated:
            s += 300
        if self.timeout:
            s += 400
        s += max(0, self.opp_score - self.my_score)
        s += self.move_errors * 2
        if self.captures == 0 and self.spawns == 0:
            s += 50
        return s

    def weakness_tags(self) -> List[str]:
        tags: List[str] = []
        if self.win:
            tags.append("win")
        else:
            tags.append("loss")
        if self.timeout:
            tags.append("timeout")
        if self.eliminated:
            tags.append("eliminated")
        if self.my_score == -1:
            tags.append("score_-1")
        if self.move_errors:
            tags.append(f"move_err_{self.move_errors}")
        if self.captures == 0:
            tags.append("no_capture")
        if self.spawns < 3:
            tags.append("low_spawn")
        return tags


def ide_url(challenge: str) -> str:
    return CHALLENGE_IDE_URL.format(public_id=challenge)


def parse_game_options(log: str) -> Optional[str]:
    block_m = re.search(r"^options:\s*(.*?)(?=^agents:)", log, re.M | re.S)
    if block_m:
        lines = [ln.strip() for ln in block_m.group(1).splitlines() if ln.strip()]
        if lines:
            return "\n".join(lines)
    seed_m = re.search(r"seed=(-?\d+)", log)
    if seed_m:
        return f"seed={seed_m.group(1)}"
    return None


def parse_log(log: str, opponent: str, game_id: Optional[int] = None) -> GameMetrics:
    seed_m = re.search(r"seed=(-?\d+)", log)
    seed = int(seed_m.group(1)) if seed_m else None
    game_options = parse_game_options(log)

    my_score, opp_score = -1, -1
    ranking: List[int] = []
    m = re.search(r"scores:\s*([^\n]+)\s*\n\s*ranking[^:]*:\s*([^\n]+)", log, re.S)
    if m:
        for part in m.group(1).split():
            if "=" in part:
                idx, val = part.split("=", 1)
                if idx == "0":
                    my_score = int(val)
                elif idx == "1":
                    opp_score = int(val)
        ranking = [int(x) for x in m.group(2).split()]

    win = bool(ranking) and ranking[0] == 0
    lines = log.splitlines()
    spawns = sum(1 for l in lines if "$0 spawned" in l)
    captures = sum(1 for l in lines if "$0 captured" in l)
    move_errors = sum(1 for l in lines if "$0: Task" in l)
    timeout = any("$0 timeout" in l or "$0: timeout" in l for l in lines)
    eliminated = any("no units or triangles left" in l and "$0" in l for l in lines)

    return GameMetrics(
        opponent=opponent,
        game_id=game_id,
        seed=seed,
        game_options=game_options,
        win=win,
        my_score=my_score,
        opp_score=opp_score,
        ranking=ranking,
        spawns=spawns,
        captures=captures,
        move_errors=move_errors,
        timeout=timeout,
        eliminated=eliminated,
        raw_scores=m.group(1) if m else "",
    )


def fetch_game_log(game_id: int) -> str:
    resp = api("GET", f"/games/{game_id}")
    if isinstance(resp, dict):
        return resp.get("log") or ""
    return str(resp)


def run_test_game(
    challenge: str,
    bot_path: Path,
    language: str,
    opponent: str,
    wait: int = 30,
    *,
    game_options: Optional[str] = None,
    replay_game_id: Optional[int] = None,
    show_in_ide: bool = False,
    overwrite_ide_game_parameters: bool = False,
    overwrite_ide_code: bool = False,
) -> GameMetrics:
    code = bot_path.read_text()
    body: Dict[str, Any] = {
        "language": language,
        "code": code,
        "show_in_ide": show_in_ide,
        "overwrite_ide_code": overwrite_ide_code,
        "overwrite_ide_game_parameters": overwrite_ide_game_parameters,
    }
    if replay_game_id is not None:
        body["replay_game_id"] = replay_game_id
    else:
        body["opponents"] = [opponent]
        if game_options:
            body["game_options"] = game_options
    resp = api("POST", f"/challenges/{challenge}/test-games", body=body, wait=wait)

    if isinstance(resp, str):
        log = resp
        game_id = None
    else:
        if resp.get("status") == "failed":
            hint = resp.get("hint", resp)
            raise SystemExit(f"Test game failed: {hint}")
        log = resp.get("log") or ""
        if not log and resp.get("test_game_id"):
            poll = api(
                "GET",
                f"/test-games/{resp['test_game_id']}",
                wait=wait,
            )
            if isinstance(poll, dict):
                log = poll.get("log") or ""
            else:
                log = str(poll)
        game_id = resp.get("test_game_id") or resp.get("game_id")

    if not log:
        raise SystemExit(f"Empty log from test game: {resp!r}")

    gid = int(game_id) if game_id is not None else None
    if gid is None:
        gm = re.search(r"^game (\d+)", log, re.M)
        if gm:
            gid = int(gm.group(1))
    return parse_log(log, opponent=opponent, game_id=gid)


def load_config_yaml(path: Path) -> dict:
    import yaml

    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_runs_jsonl(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    rows: List[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def fetch_arena_losses(challenge: str, limit: int = 20) -> List[dict]:
    """Recent ranking battles we lost (needs token)."""
    resp = api("GET", f"/challenges/{challenge}/battles?limit={limit}")
    out: List[dict] = []
    for b in resp.get("battles", []):
        if not b.get("done"):
            continue
        if b.get("my_position", 0) != 0:
            gid = b.get("game_id")
            players = {p.get("nickname"): p for p in b.get("players", [])}
            opp = next(
                (p.get("nickname") for p in b.get("players", []) if not p.get("me")),
                "?",
            )
            out.append(
                {
                    "game_id": gid,
                    "opponent": opp,
                    "ended_at": b.get("ended_at"),
                    "source": "arena",
                }
            )
    return out


def git_short_hash(cwd: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "no-git"


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2

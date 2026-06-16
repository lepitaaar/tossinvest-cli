from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .client import Credentials, TossInvestError


CONFIG_PATH = Path(os.environ.get("TOSSINVEST_CONFIG", "~/.config/tossinvest-cli/config.json")).expanduser()


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_credentials(client_id: str, client_secret: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config["client_id"] = client_id
    config["client_secret"] = client_secret
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")
    os.chmod(CONFIG_PATH, 0o600)


def get_credentials(client_id: Optional[str] = None, client_secret: Optional[str] = None) -> Credentials:
    config = load_config()
    resolved_id = client_id or os.environ.get("TOSSINVEST_CLIENT_ID") or config.get("client_id")
    resolved_secret = client_secret or os.environ.get("TOSSINVEST_CLIENT_SECRET") or config.get("client_secret")
    if not resolved_id or not resolved_secret:
        raise TossInvestError(
            "Missing credentials. Run `toss login --client-id ... --client-secret ...` or set TOSSINVEST_CLIENT_ID/TOSSINVEST_CLIENT_SECRET.",
            code="missing-credentials",
        )
    return Credentials(client_id=resolved_id, client_secret=resolved_secret)


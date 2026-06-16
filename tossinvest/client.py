from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional


DEFAULT_BASE_URL = "https://openapi.tossinvest.com"


class TossInvestError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[str] = None,
        data: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.data = data
        self.headers = dict(headers or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "message": self.message,
                "status": self.status,
                "code": self.code,
                "data": self.data,
            },
            "rateLimit": rate_limit_from_headers(self.headers),
        }


@dataclass
class Credentials:
    client_id: str
    client_secret: str


def rate_limit_from_headers(headers: Mapping[str, str]) -> Dict[str, Optional[str]]:
    return {
        "limit": headers.get("X-RateLimit-Limit"),
        "remaining": headers.get("X-RateLimit-Remaining"),
        "reset": headers.get("X-RateLimit-Reset"),
        "retryAfter": headers.get("Retry-After"),
    }


def _clean_query(params: Optional[Mapping[str, Any]]) -> str:
    if not params:
        return ""
    clean: Dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            clean[key] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            clean[key] = ",".join(str(item) for item in value)
        else:
            clean[key] = str(value)
    if not clean:
        return ""
    return "?" + urllib.parse.urlencode(clean)


class TossInvestClient:
    def __init__(
        self,
        credentials: Credentials,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 20.0,
    ) -> None:
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires_at = 0.0

    def issue_token(self) -> Dict[str, Any]:
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
            }
        ).encode()
        data, headers = self._request(
            "POST",
            "/oauth2/token",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            authenticated=False,
            unwrap=False,
        )
        token = data.get("access_token")
        if not token:
            raise TossInvestError("Token response did not include access_token", headers=headers)
        self._token = token
        expires_in = float(data.get("expires_in") or 0)
        self._token_expires_at = time.time() + max(0, expires_in - 30)
        return data

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Mapping[str, Any]] = None,
        account: Optional[str] = None,
        unwrap: bool = True,
    ) -> Dict[str, Any]:
        body = None
        headers: Dict[str, str] = {}
        if json_body is not None:
            body = json.dumps(json_body, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
        if account is not None:
            headers["X-Tossinvest-Account"] = str(account)
        return self._request(
            method,
            path + _clean_query(params),
            body=body,
            headers=headers,
            authenticated=True,
            unwrap=unwrap,
        )[0]

    def _bearer(self) -> str:
        if not self._token or time.time() >= self._token_expires_at:
            self.issue_token()
        assert self._token is not None
        return self._token

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[bytes],
        headers: Optional[Mapping[str, str]] = None,
        authenticated: bool,
        unwrap: bool,
    ) -> tuple[Dict[str, Any], Mapping[str, str]]:
        req_headers = {"Accept": "application/json", **dict(headers or {})}
        if authenticated:
            req_headers["Authorization"] = f"Bearer {self._bearer()}"

        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method.upper(),
            headers=req_headers,
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                response_headers = response.headers
                payload = json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"error": {"message": raw}}
            error = payload.get("error") if isinstance(payload, dict) else None
            raise TossInvestError(
                (error or {}).get("message") or exc.reason,
                status=exc.code,
                code=(error or {}).get("code"),
                data=(error or {}).get("data"),
                headers=exc.headers,
            ) from exc
        except urllib.error.URLError as exc:
            raise TossInvestError(str(exc.reason)) from exc

        if unwrap and isinstance(payload, dict) and "result" in payload:
            payload = payload["result"]
        return payload, response_headers

    def accounts(self) -> Dict[str, Any]:
        return self.request("GET", "/api/v1/accounts")

    def resolve_account(self, explicit: Optional[str]) -> str:
        if explicit:
            return explicit
        accounts = self.accounts()
        items: Iterable[Any]
        if isinstance(accounts, list):
            items = accounts
        else:
            items = accounts.get("accounts") or accounts.get("items") or accounts.get("result") or []
        items = list(items)
        if len(items) != 1:
            raise TossInvestError(
                "Account is required because account auto-detection did not find exactly one account",
                code="account-required",
                data={"accountCount": len(items)},
            )
        account = items[0]
        account_seq = account.get("accountSeq") if isinstance(account, dict) else None
        if not account_seq:
            raise TossInvestError("Could not find accountSeq in accounts response", code="account-seq-missing")
        return str(account_seq)


from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

from .client import DEFAULT_BASE_URL, TossInvestClient, TossInvestError
from .config import CONFIG_PATH, get_credentials, save_credentials


def emit(payload: Any, *, pretty: bool = False) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":")))


def ok(result: Any, *, command: str, raw: bool = False) -> Dict[str, Any]:
    if raw:
        return result
    return {"ok": True, "command": command, "result": result}


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--raw", action="store_true", help="Return the API response body without CLI envelope.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Override Open API base URL.")
    parser.add_argument("--client-id", help="Client ID override.")
    parser.add_argument("--client-secret", help="Client secret override.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="toss", description="AI-first CLI for Toss Securities Open API.")
    add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("schema", help="Print machine-readable command schema.")

    login = sub.add_parser("login", help="Store API credentials.")
    login.add_argument("--client-id", required=True)
    login.add_argument("--client-secret", required=True)

    sub.add_parser("token", help="Issue an OAuth2 access token.")
    sub.add_parser("accounts", aliases=["account-list"], help="List accounts.")

    holdings = sub.add_parser("holdings", aliases=["positions"], help="List account holdings.")
    holdings.add_argument("--account")
    holdings.add_argument("--symbol")

    status = sub.add_parser("status", help="Account snapshot: accounts, holdings, buying power, open orders.")
    status.add_argument("--account")
    status.add_argument("--currency", default="KRW")

    price = sub.add_parser("price", aliases=["quote"], help="Get current prices for one or more symbols.")
    price.add_argument("symbols", nargs="+")

    orderbook = sub.add_parser("orderbook", help="Get orderbook for a symbol.")
    orderbook.add_argument("symbol")

    trades = sub.add_parser("trades", help="Get recent trades for a symbol.")
    trades.add_argument("symbol")
    trades.add_argument("--count", type=int)

    candles = sub.add_parser("candles", help="Get candles for a symbol.")
    candles.add_argument("symbol")
    candles.add_argument("--interval", required=True, choices=["1m", "1d"])
    candles.add_argument("--count", type=int)
    candles.add_argument("--before")
    candles.add_argument("--adjusted", action="store_true")

    limits = sub.add_parser("price-limits", help="Get price limits for a symbol.")
    limits.add_argument("symbol")

    stocks = sub.add_parser("stocks", help="Get stock reference info.")
    stocks.add_argument("symbols", nargs="+")

    warnings = sub.add_parser("warnings", help="Get stock warnings.")
    warnings.add_argument("symbol")

    fx = sub.add_parser("exchange-rate", help="Get exchange rate.")
    fx.add_argument("--base", dest="base_currency", required=True)
    fx.add_argument("--quote", dest="quote_currency", required=True)
    fx.add_argument("--date-time")

    cal = sub.add_parser("calendar", help="Get market calendar.")
    cal.add_argument("market", choices=["KR", "US"])
    cal.add_argument("--date")

    buying = sub.add_parser("buying-power", help="Get buying power.")
    buying.add_argument("--account")
    buying.add_argument("--currency", required=True)

    sellable = sub.add_parser("sellable", help="Get sellable quantity.")
    sellable.add_argument("--account")
    sellable.add_argument("--symbol", required=True)

    commissions = sub.add_parser("commissions", help="Get commissions.")
    commissions.add_argument("--account")

    orders = sub.add_parser("orders", help="List orders.")
    orders.add_argument("--account")
    orders.add_argument("--status", required=True, choices=["OPEN", "CLOSED"])
    orders.add_argument("--symbol")
    orders.add_argument("--from")
    orders.add_argument("--to")
    orders.add_argument("--cursor")
    orders.add_argument("--limit", type=int)

    order_get = sub.add_parser("order-get", help="Get one order.")
    order_get.add_argument("--account")
    order_get.add_argument("--order-id", required=True)

    for name, side in (("buy", "BUY"), ("sell", "SELL")):
        p = sub.add_parser(name, help=f"Create a {side.lower()} order.")
        add_order_create_args(p)
        p.set_defaults(side=side)

    create = sub.add_parser("order-create", help="Create an order with explicit side.")
    add_order_create_args(create)
    create.add_argument("--side", required=True, choices=["BUY", "SELL"])

    modify = sub.add_parser("order-modify", help="Modify an order.")
    modify.add_argument("--account")
    modify.add_argument("--order-id", required=True)
    modify.add_argument("--order-type", required=True, choices=["LIMIT", "MARKET"])
    modify.add_argument("--quantity")
    modify.add_argument("--price")
    modify.add_argument("--confirm-high-value-order", action="store_true")

    cancel = sub.add_parser("order-cancel", help="Cancel an order.")
    cancel.add_argument("--account")
    cancel.add_argument("--order-id", required=True)

    add_subcommand_common_options(sub)
    return parser


def add_subcommand_common_options(subparsers: argparse._SubParsersAction) -> None:
    seen = set()
    for name, child in subparsers.choices.items():
        if id(child) in seen:
            continue
        seen.add(id(child))
        child.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        child.add_argument("--raw", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        child.add_argument("--base-url", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        if name != "login":
            child.add_argument("--client-id", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
            child.add_argument("--client-secret", default=argparse.SUPPRESS, help=argparse.SUPPRESS)


def add_order_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--account")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--order-type", required=True, choices=["LIMIT", "MARKET"])
    parser.add_argument("--quantity", help="Share quantity for quantity-based orders.")
    parser.add_argument("--amount", help="USD order amount for US market amount-based MARKET orders.")
    parser.add_argument("--price")
    parser.add_argument("--time-in-force", choices=["DAY", "CLS"])
    parser.add_argument("--client-order-id")
    parser.add_argument("--confirm-high-value-order", action="store_true")


def client_from_args(args: argparse.Namespace) -> TossInvestClient:
    return TossInvestClient(
        get_credentials(args.client_id, args.client_secret),
        base_url=args.base_url,
    )


def account(client: TossInvestClient, value: Optional[str]) -> str:
    return client.resolve_account(value)


def order_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if bool(args.quantity) == bool(args.amount):
        raise TossInvestError("Provide exactly one of --quantity or --amount.", code="invalid-order-quantity")
    payload: Dict[str, Any] = {
        "symbol": args.symbol,
        "side": args.side,
        "orderType": args.order_type,
    }
    if args.client_order_id:
        payload["clientOrderId"] = args.client_order_id
    if args.time_in_force:
        payload["timeInForce"] = args.time_in_force
    if args.quantity:
        payload["quantity"] = args.quantity
    if args.amount:
        payload["orderAmount"] = args.amount
    if args.price:
        payload["price"] = args.price
    if args.confirm_high_value_order:
        payload["confirmHighValueOrder"] = True
    return payload


def run(args: argparse.Namespace) -> Any:
    cmd = args.command
    if cmd == "schema":
        return command_schema()
    if cmd == "login":
        save_credentials(args.client_id, args.client_secret)
        return {"ok": True, "command": cmd, "result": {"configPath": str(CONFIG_PATH), "stored": True}}

    client = client_from_args(args)

    if cmd == "token":
        return ok(client.issue_token(), command=cmd, raw=args.raw)
    if cmd in {"accounts", "account-list"}:
        return ok(client.accounts(), command=cmd, raw=args.raw)
    if cmd in {"holdings", "positions"}:
        result = client.request("GET", "/api/v1/holdings", params={"symbol": args.symbol}, account=account(client, args.account), unwrap=not args.raw)
    elif cmd == "status":
        resolved = account(client, args.account)
        result = {
            "accountSeq": resolved,
            "holdings": client.request("GET", "/api/v1/holdings", account=resolved),
            "buyingPower": client.request("GET", "/api/v1/buying-power", params={"currency": args.currency}, account=resolved),
            "openOrders": client.request("GET", "/api/v1/orders", params={"status": "OPEN"}, account=resolved),
        }
    elif cmd in {"price", "quote"}:
        result = client.request("GET", "/api/v1/prices", params={"symbols": args.symbols}, unwrap=not args.raw)
    elif cmd == "orderbook":
        result = client.request("GET", "/api/v1/orderbook", params={"symbol": args.symbol}, unwrap=not args.raw)
    elif cmd == "trades":
        result = client.request("GET", "/api/v1/trades", params={"symbol": args.symbol, "count": args.count}, unwrap=not args.raw)
    elif cmd == "candles":
        result = client.request(
            "GET",
            "/api/v1/candles",
            params={
                "symbol": args.symbol,
                "interval": args.interval,
                "count": args.count,
                "before": args.before,
                "adjusted": args.adjusted if args.adjusted else None,
            },
            unwrap=not args.raw,
        )
    elif cmd == "price-limits":
        result = client.request("GET", "/api/v1/price-limits", params={"symbol": args.symbol}, unwrap=not args.raw)
    elif cmd == "stocks":
        result = client.request("GET", "/api/v1/stocks", params={"symbols": args.symbols}, unwrap=not args.raw)
    elif cmd == "warnings":
        result = client.request("GET", f"/api/v1/stocks/{args.symbol}/warnings", unwrap=not args.raw)
    elif cmd == "exchange-rate":
        result = client.request(
            "GET",
            "/api/v1/exchange-rate",
            params={"baseCurrency": args.base_currency, "quoteCurrency": args.quote_currency, "dateTime": args.date_time},
            unwrap=not args.raw,
        )
    elif cmd == "calendar":
        result = client.request("GET", f"/api/v1/market-calendar/{args.market}", params={"date": args.date}, unwrap=not args.raw)
    elif cmd == "buying-power":
        result = client.request("GET", "/api/v1/buying-power", params={"currency": args.currency}, account=account(client, args.account), unwrap=not args.raw)
    elif cmd == "sellable":
        result = client.request("GET", "/api/v1/sellable-quantity", params={"symbol": args.symbol}, account=account(client, args.account), unwrap=not args.raw)
    elif cmd == "commissions":
        result = client.request("GET", "/api/v1/commissions", account=account(client, args.account), unwrap=not args.raw)
    elif cmd == "orders":
        result = client.request(
            "GET",
            "/api/v1/orders",
            params={"status": args.status, "symbol": args.symbol, "from": args.__dict__.get("from"), "to": args.to, "cursor": args.cursor, "limit": args.limit},
            account=account(client, args.account),
            unwrap=not args.raw,
        )
    elif cmd == "order-get":
        result = client.request("GET", f"/api/v1/orders/{args.order_id}", account=account(client, args.account), unwrap=not args.raw)
    elif cmd in {"buy", "sell", "order-create"}:
        result = client.request("POST", "/api/v1/orders", json_body=order_payload(args), account=account(client, args.account), unwrap=not args.raw)
    elif cmd == "order-modify":
        body: Dict[str, Any] = {"orderType": args.order_type}
        if args.quantity:
            body["quantity"] = args.quantity
        if args.price:
            body["price"] = args.price
        if args.confirm_high_value_order:
            body["confirmHighValueOrder"] = True
        result = client.request("POST", f"/api/v1/orders/{args.order_id}/modify", json_body=body, account=account(client, args.account), unwrap=not args.raw)
    elif cmd == "order-cancel":
        result = client.request("POST", f"/api/v1/orders/{args.order_id}/cancel", account=account(client, args.account), unwrap=not args.raw)
    else:
        raise TossInvestError(f"Unsupported command: {cmd}", code="unsupported-command")

    return ok(result, command=cmd, raw=args.raw)


def command_schema() -> Dict[str, Any]:
    return {
        "ok": True,
        "command": "schema",
        "result": {
            "output": "json",
            "auth": {
                "credentialSources": ["login config", "TOSSINVEST_CLIENT_ID/TOSSINVEST_CLIENT_SECRET", "--client-id/--client-secret"],
                "accountHeader": "Use --account with accountSeq. If omitted, CLI auto-selects only when exactly one account exists.",
            },
            "commands": [
                {"name": "login", "purpose": "store credentials", "requiresAuth": False},
                {"name": "token", "purpose": "issue OAuth2 token", "requiresAuth": False},
                {"name": "accounts", "aliases": ["account-list"], "purpose": "list accounts", "requiresAccount": False},
                {"name": "holdings", "aliases": ["positions"], "purpose": "list holdings", "requiresAccount": True},
                {"name": "status", "purpose": "holdings + buying power + open orders", "requiresAccount": True},
                {"name": "price", "aliases": ["quote"], "purpose": "current prices", "params": ["symbols..."]},
                {"name": "orderbook", "purpose": "orderbook", "params": ["symbol"]},
                {"name": "trades", "purpose": "recent trades", "params": ["symbol", "--count"]},
                {"name": "candles", "purpose": "candles", "params": ["symbol", "--interval 1m|1d", "--count", "--before", "--adjusted"]},
                {"name": "stocks", "purpose": "stock reference info", "params": ["symbols..."]},
                {"name": "warnings", "purpose": "stock warnings", "params": ["symbol"]},
                {"name": "exchange-rate", "purpose": "KRW/USD exchange rate", "params": ["--base", "--quote", "--date-time"]},
                {"name": "calendar", "purpose": "market calendar", "params": ["KR|US", "--date"]},
                {"name": "buying-power", "purpose": "available cash", "requiresAccount": True, "params": ["--currency"]},
                {"name": "sellable", "purpose": "sellable quantity", "requiresAccount": True, "params": ["--symbol"]},
                {"name": "commissions", "purpose": "commission info", "requiresAccount": True},
                {"name": "orders", "purpose": "list orders", "requiresAccount": True, "params": ["--status OPEN|CLOSED"]},
                {"name": "order-get", "purpose": "order detail", "requiresAccount": True, "params": ["--order-id"]},
                {"name": "buy", "purpose": "create BUY order", "requiresAccount": True, "params": ["--symbol", "--order-type", "--quantity or --amount", "--price"]},
                {"name": "sell", "purpose": "create SELL order", "requiresAccount": True, "params": ["--symbol", "--order-type", "--quantity", "--price"]},
                {"name": "order-create", "purpose": "create order with explicit side", "requiresAccount": True},
                {"name": "order-modify", "purpose": "modify order", "requiresAccount": True, "params": ["--order-id", "--order-type", "--quantity", "--price"]},
                {"name": "order-cancel", "purpose": "cancel order", "requiresAccount": True, "params": ["--order-id"]},
            ],
        },
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        emit(run(args), pretty=args.pretty)
        return 0
    except TossInvestError as exc:
        emit(exc.to_dict(), pretty=args.pretty)
        return 1
    except KeyboardInterrupt:
        emit({"ok": False, "error": {"message": "Interrupted", "code": "interrupted"}}, pretty=args.pretty)
        return 130


if __name__ == "__main__":
    sys.exit(main())

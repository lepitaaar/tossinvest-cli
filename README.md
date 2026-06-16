# tossinvest-ai-cli

AI 에이전트가 토스증권 Open API를 안정적으로 호출하기 위한 JSON-first CLI입니다.

## 설치 없이 실행

```bash
python3 -m tossinvest.cli --help
```

## 개발 설치

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
toss --help
```

## 인증

API key와 secret을 저장합니다.

```bash
toss login --client-id "$TOSS_CLIENT_ID" --client-secret "$TOSS_CLIENT_SECRET"
```

환경변수만으로도 동작합니다.

```bash
export TOSSINVEST_CLIENT_ID="..."
export TOSSINVEST_CLIENT_SECRET="..."
```

모든 명령의 기본 출력은 JSON입니다. 실패도 JSON으로 내려가므로 AI가 파싱하기 쉽습니다.

## 기본 명령

```bash
toss schema
toss token
toss accounts
toss holdings --account 1
toss status --account 1
toss price 005930 AAPL
toss quote 005930 AAPL
toss orderbook 005930
toss trades AAPL --count 20
toss stocks 005930 AAPL
toss warnings 005930
toss exchange-rate --base KRW --quote USD
toss calendar KR
toss buying-power --account 1 --currency KRW
toss sellable --account 1 --symbol 005930
toss commissions --account 1
toss orders --account 1 --status OPEN
toss order-get --account 1 --order-id ORDER_ID
```

## 매매

수량 기반 매수/매도:

```bash
toss buy --account 1 --symbol 005930 --quantity 1 --order-type LIMIT --price 70000
toss sell --account 1 --symbol AAPL --quantity 1 --order-type MARKET
```

미국 주식 금액 기반 시장가 매수:

```bash
toss buy --account 1 --symbol AAPL --amount 100.5 --order-type MARKET
```

정정/취소:

```bash
toss order-modify --account 1 --order-id ORDER_ID --order-type LIMIT --quantity 2 --price 71000
toss order-cancel --account 1 --order-id ORDER_ID
```

## AI 친화적 설계

- 출력은 기본적으로 compact JSON입니다.
- `--pretty`로 사람이 보기 좋은 JSON을 출력할 수 있습니다.
- `--raw`는 API 원본 envelope을 그대로 출력합니다.
- 계좌가 하나뿐이면 `--account` 생략 시 자동 선택합니다.
- `--client-order-id`로 주문 멱등성을 지정할 수 있습니다.
- `--confirm-high-value-order`로 고액 주문 확인 플래그를 보낼 수 있습니다.

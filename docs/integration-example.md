# PesoWay simulated integration

Use a restricted server-side API key; never place it in browser JavaScript or a mobile app bundle.

```bash
curl -X POST http://localhost:8000/api/v1/payment-intents/ \
  -H "Authorization: Bearer $PESOWAY_API_KEY" \
  -H "Idempotency-Key: order-2026-0001-create" \
  -H "Content-Type: application/json" \
  -d '{"amount_centavos":12500,"currency":"PHP","merchant_reference":"order-2026-0001","description":"Simulated order"}'
```

Save the returned `data.id` and query it only from trusted server code. Retry a timed-out create request using the exact same `Idempotency-Key` and body. A changed body with the same key correctly returns HTTP 409.

For webhooks, verify `X-PesoWay-Timestamp` is recent, calculate HMAC-SHA256 over `<timestamp>.<raw request body>` using your endpoint secret, compare in constant time, and persist the event ID before processing it. Respond with a 2xx only after your transaction commits.

The prototype does not accept customer payment-success input. Its `PaymentAttempt` and provider simulation lifecycle remains intentionally incomplete until a controlled simulator is introduced.

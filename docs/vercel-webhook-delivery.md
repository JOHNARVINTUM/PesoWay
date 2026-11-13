# Vercel webhook delivery

PesoWay uses a PostgreSQL-backed transactional outbox. Payment services create a
`WebhookEvent` and matching `WebhookDelivery` rows; no request to a merchant is
made within the database transaction. The scheduler processes only pending rows
whose `next_attempt_at` is due. It signs each raw JSON payload and preserves the
existing exponential retry policy (up to five attempts).

## Production configuration

Set these environment variables in the **PesoWay Vercel project**, for the
Production environment. Do not put any of them in source control or frontend
code.

- `DJANGO_SECRET_KEY`
- `DATABASE_URL` (the production PostgreSQL connection URL)
- `WEBHOOK_ENCRYPTION_KEY`
- `CRON_SECRET` (a random, header-safe value of at least 16 characters)
- `DJANGO_DEBUG=false`
- `DJANGO_ALLOWED_HOSTS` (include the deployed PesoWay host)
- `DJANGO_SECURE_SSL_REDIRECT=true`

`CRON_SECRET` is compared in constant time. The internal route is:

`GET /internal/cron/deliver-webhooks/`

It accepts only `Authorization: Bearer <CRON_SECRET>`. Missing or invalid
credentials receive the same generic `401` response. The route accepts no
secrets in query parameters and returns processed/succeeded/failed counts only
after successful authentication.

## Vercel Cron configuration

`vercel.json` registers the route at `0 0 * * *` (UTC). Vercel Cron calls the
production deployment with an HTTP GET request and automatically supplies
`Authorization: Bearer <CRON_SECRET>` when that environment variable exists.
After deployment, verify it under **Project → Schedules → Cron Jobs** and make
sure Cron Jobs are enabled.

Do not add the secret to a URL. To test manually after deployment, use a local
shell variable and a header (do not paste the secret into ticketing systems or
browser URLs):

```powershell
$cronSecret = $env:CRON_SECRET
Invoke-RestMethod -Method Get -Uri "https://YOUR-PESOWAY-HOST/internal/cron/deliver-webhooks/" -Headers @{ Authorization = "Bearer $cronSecret" }
```

## Plan limitation and recommended operation

Vercel Hobby permits Cron only once per day and provides per-hour timing
precision. The daily schedule is intentionally used so a Hobby deployment does
not fail configuration validation. It means a simulated successful checkout may
wait until the next cron invocation before BUILTASUPPLY receives its webhook;
this is not suitable for timely order fulfillment.

For a production-like simulator, use Vercel Pro and change the schedule to a
bounded frequent interval such as `*/5 * * * *`, while keeping the same outbox
and endpoint. Vercel Cron is at-least-once, so the endpoint and receiver must
remain idempotent. The existing unique delivery constraint, transactional claim,
and successful-delivery status prevent PesoWay from resending a completed
delivery through ordinary scheduler repeats. BUILTASUPPLY must continue to
deduplicate by the signed event ID before moving an eligible order from PENDING
to PAID.

The `python manage.py deliver_webhooks` command remains useful for local
development, one-off recovery, and non-Vercel workers. It now calls the same
shared batch service as the cron route; deployed Vercel delivery should use the
protected route instead of attempting to run a shell command.

## Deployment checklist

1. Configure the required Production environment variables in Vercel.
2. Deploy PesoWay and confirm the registered Cron route in the Schedules UI.
3. Register BUILTASUPPLY's HTTPS receiver as a PesoWay webhook endpoint, with
   `payment_intent.succeeded` subscribed.
4. Complete a simulated checkout and inspect PesoWay webhook event/delivery
   history plus BUILTASUPPLY's verified order state.
5. If using Hobby, expect the daily delay. Use Pro or an independently operated,
   authenticated scheduler for shorter simulated delivery intervals.

No real payment provider or real-money processing is involved.

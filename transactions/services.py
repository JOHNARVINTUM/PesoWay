from .models import LedgerEntry


def record_entry(*, merchant, payment_intent, entry_type: str, amount_centavos: int, reference: str, metadata: dict | None = None) -> LedgerEntry:
    return LedgerEntry.objects.create(
        merchant=merchant, payment_intent=payment_intent, entry_type=entry_type,
        amount_centavos=amount_centavos, currency="PHP", reference=reference, metadata=metadata or {},
    )

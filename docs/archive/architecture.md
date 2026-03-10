
## Truth chain (anti-drift)

- public.event_log is the canonical ledger of record.
- public.apply_envelope is the only permitted write gate into event_log.
- public.booking_state is a derived read model (projection) and must never be treated as a source of truth.
- Any write to booking_state is valid only if it is produced by apply_envelope as part of applying envelopes.

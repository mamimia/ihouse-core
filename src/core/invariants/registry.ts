export type InvariantSeverity = "BLOCK_DEPLOY" | "WARN";

export type DomainInvariant = {
  id: string;
  description: string;
  scope: "projection" | "aggregate" | "ingest" | "rebuild";
  severity: InvariantSeverity;
  proofs: string[]; // test names that enforce it
};

export const DOMAIN_INVARIANTS: DomainInvariant[] = [
  {
    id: "INV_BOOKING_NO_OVERLAP",
    description: "No overlapping bookings for the same property and time range (until unit_id exists), unless explicitly allowed.",
    scope: "projection",
    severity: "BLOCK_DEPLOY",
    proofs: ["invariants booking no overlap"]
  },
  {
    id: "INV_BOOKING_STATE_GRAPH",
    description: "Booking status transitions must follow the allowed transition graph.",
    scope: "aggregate",
    severity: "BLOCK_DEPLOY",
    proofs: ["invariants booking state graph"]
  },
  {
    id: "INV_REPLAY_ORDER_ROW_ID_ASC",
    description: "Replay applies events strictly by row_id ASC.",
    scope: "rebuild",
    severity: "BLOCK_DEPLOY",
    proofs: ["invariants replay order row id asc"]
  },
  {
    id: "INV_EVENT_ID_IDEMPOTENCY",
    description: "Event idempotency is enforced via unique(event_id).",
    scope: "ingest",
    severity: "BLOCK_DEPLOY",
    proofs: ["invariants event id uniqueness"]
  },
  {
    id: "INV_PROPERTY_EXISTS_ON_INGEST",
    description: "Property must exist for any property scoped ingest event.",
    scope: "ingest",
    severity: "BLOCK_DEPLOY",
    proofs: ["invariants property exists on ingest"]
  }
];

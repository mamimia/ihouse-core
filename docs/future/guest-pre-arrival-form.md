# Future Capability — Guest-Initiated Pre-Arrival Form

**Status:** Intentionally deferred — not a current bug, not a missing build  
**Category:** Guest Experience / Pre-Arrival  
**Item reference:** Item 9 (active-fix stream deferred)  
**Date noted:** 2026-04-04  

---

## What this is

A guest-initiated or guest-completable pre-arrival form tied to a confirmed stay,
allowing guests to submit key information before check-in. That information flows
into the guest dossier and stay thread for the operational team.

---

## Why it is deferred now

The system is currently **iCal-first** in the majority of real bookings.

In iCal-only mode, what we reliably receive per booking is:

| Data point | Available via iCal |
|---|---|
| Booking timing (check-in / check-out dates) | ✅ Usually |
| Property / villa identity | ✅ Usually |
| Booking reference / source context | ✅ Partial |
| Guest legal name | ⚠️ Sometimes, often incomplete |
| Guest email address | ❌ Usually not |
| Guest phone number | ❌ Usually not |
| Trusted direct reach path to guest | ❌ Not at all |

### What this means in practice

Without a reliable email, phone, or trusted identity, we cannot:
- Know we have the right guest before issuing them a pre-arrival link
- Prevent form data from being submitted by the wrong person
- Associate form responses with the correct booking with high confidence
- Send the link securely (no recipient address to send to)

A pre-arrival form issued without guest identity confidence is either:
- **Leaked to the wrong person** (no email → could go anywhere)
- **Never received** (no verified contact = no delivery path)
- **Unanswered** (no way for the guest to know it exists)

This is not a gap in our implementation. It is a fundamental constraint of the
iCal data model.

---

## Why it is still strategically important

Even though it is deferred, this capability is genuinely valuable:

- **Pre-arrival data reduces check-in friction.** When the team knows who is
  arriving, their arrival time, their preferences, and whether they have outstanding
  document requirements, check-in is faster and more professional.

- **Guest dossier quality.** Pre-arrival data enriches the stay record — contact
  details, arrival flight, guest count, document status, and preference notes are
  all things the OM would otherwise need to chase manually or leave blank.

- **Trust and experience signal.** A clean pre-arrival touchpoint with the guest
  (at the right moment) is a premium hospitality signal. It sets the tone before
  arrival.

- **Reduces back-and-forth.** Without it, staff often collect the same information
  via LINE, WhatsApp, or phone call — fragmented and not recorded in the system.

---

## What the intended future model should support

When this capability is built, it should handle:

1. **Structured pre-arrival data submission** — not a free-text chat. A defined
   set of fields the guest fills in: arrival time, total guest count, document
   delivery confirmation, preferences, any special requests.

2. **Flow into the guest dossier and stay thread.** Submitted data must be
   visible to the OM in the stay context, not just in a standalone form inbox.
   The OM should see it as part of the stay record, not a separate tool.

3. **Strong stay linkage.** The form must be cryptographically tied to a specific
   booking, expiry-controlled, and non-transferable. The same token model used
   for guest portal and guest checkout applies here.

4. **Identity confidence gate.** The system should only issue a pre-arrival form
   link when it has a verified or trusted reach path — not speculatively.

5. **Structured output, not prose.** Arrival time field. Guest count field.
   Document acknowledgement checkbox. Not an open text box.

6. **Graceful display.** If the guest has already filled it in, re-opening the
   link should show a confirmation / summary, not an empty form.

---

## What would make this viable

The strong version of this feature becomes viable when we have one or more of the
following:

| Dependency | Why it helps |
|---|---|
| **OTA API access** | OTA APIs (Airbnb Host API, Booking.com Connectivity API) include verified guest email and sometimes phone. Identity becomes available at booking confirmation. |
| **OTA messaging integration** | OTA messaging threads (Airbnb messages, Booking.com inbox) give a verified delivery path. We can send links inside the existing thread the guest is already monitoring. |
| **Richer guest identity than iCal** | If a direct booking channel or CRM provides verified email and name at time of booking, the form can be issued immediately with high confidence. |
| **Manual invite after verified contact exists** | Even under iCal, if the OM has already made contact with the guest via LINE or WhatsApp and the guest has replied with a phone or email, a staff-generated invite can be issued safely. |

---

## Possible interim path (not active, for later consideration)

A lower-risk interim version that could be built before full OTA integration:

**Manual staff-generated invite flow.**

1. OM or admin confirms a verified contact path exists for the guest (e.g. they
   already have the guest's WhatsApp or email from a message exchange).
2. OM triggers "Send pre-arrival form" from the booking dossier.
3. System generates a time-limited, booking-scoped, cryptographically signed link
   (same GUEST_PORTAL / GUEST_CHECKOUT token model already in place).
4. OM delivers the link manually via their existing channel (WhatsApp, LINE, email).
5. Guest fills in the form. Data flows into the dossier and stay thread.

This does not solve the zero-contact problem — it assumes the OM already has the
guest. But it converts a manual back-and-forth into a structured, recorded
pre-arrival intake.

> This is noted here for future planning only. It is not part of the current
> active build and should not be started unless explicitly requested.

---

## What this is NOT

| Claim | Correct answer |
|---|---|
| "This is a missing feature we forgot" | No. It was evaluated and deferred deliberately. |
| "This is a current bug" | No. Nothing is broken. The current system handles what iCal provides correctly. |
| "This should be in the current active phase" | No. It belongs here, in the deferred future docs, until the underlying identity dependencies exist. |

---

## When to revisit

Revisit this document when any of the following is true:

- OTA API integration (Airbnb or Booking.com) moves into active planning
- A direct booking channel is added that provides verified guest email
- The manual invite interim path is explicitly requested by the operator
- Guest identity enrichment (via CRM or direct-booking flow) becomes a live feature

Until then: **this is intentionally deferred, correctly documented, and not on the
active-fix or current-build list.**

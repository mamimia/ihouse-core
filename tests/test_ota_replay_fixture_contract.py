"""
Phase 91 — OTA Replay Fixture Contract Tests

Loads static YAML fixture files from tests/fixtures/ota_replay/ and
replays each recorded OTA payload through the full production pipeline.

Verifies:
  - Fixture produces the expected canonical envelope type
  - Envelope provider field matches expectation
  - Envelope tenant_id is preserved
  - idempotency_key is non-empty and contains the provider name
  - Replaying the same fixture twice produces identical idempotency_key
  - Envelope produced is a CanonicalEnvelope dataclass

Structure:
  Group A — Fixture loading: all 11 provider YAML files are loadable
  Group B — Per-fixture replay: each fixture produces the expected envelope
  Group C — Fixture replay determinism: same fixture → same idempotency_key
  Group D — Fixture mutation: changing event_id changes the idempotency_key
  Group E — Fixture coverage invariant: each provider has CREATE + CANCEL
"""
from __future__ import annotations

import copy
import pathlib
from typing import Any, Dict, List

import pytest
import yaml

from adapters.ota.pipeline import process_ota_event
from adapters.ota.schemas import CanonicalEnvelope

# ---------------------------------------------------------------------------
# Fixture loading infrastructure
# ---------------------------------------------------------------------------

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "ota_replay"

EXPECTED_PROVIDERS = [
    "bookingcom", "expedia", "airbnb", "agoda",
    "tripcom", "vrbo", "gvr", "traveloka", "makemytrip", "klook", "despegar",
]


def _load_fixtures_for(provider: str) -> List[Dict[str, Any]]:
    """Load all YAML documents from a provider fixture file."""
    fixture_file = FIXTURE_DIR / f"{provider}.yaml"
    with fixture_file.open() as f:
        docs = list(yaml.safe_load_all(f))
    return [d for d in docs if d is not None]


def _load_all_fixtures() -> List[Dict[str, Any]]:
    """Load all fixtures from all provider files."""
    fixtures = []
    for provider in EXPECTED_PROVIDERS:
        fixtures.extend(_load_fixtures_for(provider))
    return fixtures


def _run_fixture(fixture: Dict[str, Any]) -> CanonicalEnvelope:
    """Run a single fixture through the pipeline."""
    provider = fixture["provider"]
    payload = dict(fixture["payload"])
    tenant_id = payload.get("tenant_id", "tenant-replay-default")
    return process_ota_event(provider, payload, tenant_id)


ALL_FIXTURES = _load_all_fixtures()
FIXTURE_IDS = [f"{f['provider']}:{f['label']}" for f in ALL_FIXTURES]


# ---------------------------------------------------------------------------
# Group A — Fixture loading
# ---------------------------------------------------------------------------

class TestGroupAFixtureLoading:

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_a1_fixture_file_exists(self, provider: str) -> None:
        fixture_file = FIXTURE_DIR / f"{provider}.yaml"
        assert fixture_file.exists(), f"Missing fixture file: {fixture_file}"

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_a2_fixture_file_is_valid_yaml(self, provider: str) -> None:
        docs = _load_fixtures_for(provider)
        assert len(docs) > 0, f"{provider}: fixture file is empty"

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_a3_each_fixture_has_required_keys(self, provider: str) -> None:
        docs = _load_fixtures_for(provider)
        for doc in docs:
            assert "provider" in doc, f"{provider}: missing 'provider'"
            assert "label" in doc, f"{provider}: missing 'label'"
            assert "payload" in doc, f"{provider}: missing 'payload'"
            assert "expected" in doc, f"{provider}: missing 'expected'"

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_a4_fixture_provider_field_matches_filename(self, provider: str) -> None:
        docs = _load_fixtures_for(provider)
        for doc in docs:
            assert doc["provider"] == provider, (
                f"Fixture provider mismatch: expected '{provider}', got '{doc['provider']}'"
            )

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_a5_payload_has_occurred_at(self, provider: str) -> None:
        docs = _load_fixtures_for(provider)
        for doc in docs:
            assert "occurred_at" in doc["payload"], (
                f"{provider}/{doc['label']}: missing occurred_at"
            )


# ---------------------------------------------------------------------------
# Group B — Per-fixture replay: expected envelope
# ---------------------------------------------------------------------------

class TestGroupBFixtureReplay:

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_b1_envelope_type_matches_expectation(self, fixture: Dict[str, Any]) -> None:
        envelope = _run_fixture(fixture)
        expected_type = fixture["expected"]["type"]
        assert envelope.type == expected_type, (
            f"{fixture['label']}: expected type={expected_type!r}, got {envelope.type!r}"
        )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_b2_envelope_is_canonical_envelope(self, fixture: Dict[str, Any]) -> None:
        envelope = _run_fixture(fixture)
        assert isinstance(envelope, CanonicalEnvelope)

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_b3_payload_provider_field_matches(self, fixture: Dict[str, Any]) -> None:
        envelope = _run_fixture(fixture)
        expected_provider = fixture["expected"]["provider"]
        assert envelope.payload.get("provider") == expected_provider

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_b4_tenant_id_preserved(self, fixture: Dict[str, Any]) -> None:
        envelope = _run_fixture(fixture)
        expected_tenant = fixture["expected"]["tenant_id"]
        assert envelope.tenant_id == expected_tenant

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_b5_idempotency_key_contains_provider(self, fixture: Dict[str, Any]) -> None:
        envelope = _run_fixture(fixture)
        expected_fragment = fixture["expected"]["idempotency_key_contains"]
        assert expected_fragment in str(envelope.idempotency_key), (
            f"{fixture['label']}: idempotency_key={envelope.idempotency_key!r} "
            f"does not contain '{expected_fragment}'"
        )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_b6_reservation_id_in_envelope(self, fixture: Dict[str, Any]) -> None:
        envelope = _run_fixture(fixture)
        assert "reservation_id" in envelope.payload
        assert envelope.payload["reservation_id"]

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_b7_property_id_in_envelope(self, fixture: Dict[str, Any]) -> None:
        envelope = _run_fixture(fixture)
        assert "property_id" in envelope.payload
        assert envelope.payload["property_id"]

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_b8_occurred_at_non_null(self, fixture: Dict[str, Any]) -> None:
        envelope = _run_fixture(fixture)
        assert envelope.occurred_at is not None


# ---------------------------------------------------------------------------
# Group C — Replay determinism: same fixture → same idempotency_key
# ---------------------------------------------------------------------------

class TestGroupCReplayDeterminism:

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_c1_idempotency_key_is_stable_across_two_runs(
        self, fixture: Dict[str, Any]
    ) -> None:
        env1 = _run_fixture(fixture)
        env2 = _run_fixture(fixture)
        assert env1.idempotency_key == env2.idempotency_key, (
            f"{fixture['label']}: idempotency_key differs between runs: "
            f"{env1.idempotency_key!r} vs {env2.idempotency_key!r}"
        )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_c2_envelope_type_is_stable_across_two_runs(
        self, fixture: Dict[str, Any]
    ) -> None:
        env1 = _run_fixture(fixture)
        env2 = _run_fixture(fixture)
        assert env1.type == env2.type

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_c3_reservation_id_is_stable_across_two_runs(
        self, fixture: Dict[str, Any]
    ) -> None:
        env1 = _run_fixture(fixture)
        env2 = _run_fixture(fixture)
        assert env1.payload["reservation_id"] == env2.payload["reservation_id"]


# ---------------------------------------------------------------------------
# Group D — Fixture mutation: changing event_id changes idempotency_key
# ---------------------------------------------------------------------------

class TestGroupDFixtureMutation:

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=FIXTURE_IDS)
    def test_d1_different_event_id_produces_different_idempotency_key(
        self, fixture: Dict[str, Any]
    ) -> None:
        """Changing the external event identifier must change the idempotency_key.

        id_field: the event identifier field name varies by provider:
          - traveloka  → event_reference
          - makemytrip → event_id  (standard)
          - klook      → event_id  (standard)
          - despegar   → event_id  (standard)
          - all others → event_id  (standard)
        """
        original_envelope = _run_fixture(fixture)

        # Determine which field drives the idempotency key for this provider
        provider = fixture["provider"]
        id_field = "event_reference" if provider == "traveloka" else "event_id"

        # Mutate: clone fixture with a different event identifier
        mutated_fixture = copy.deepcopy(fixture)
        original_id = mutated_fixture["payload"].get(id_field, "evt-original")
        mutated_fixture["payload"][id_field] = original_id + "-MUTATED"

        mutated_envelope = _run_fixture(mutated_fixture)

        assert original_envelope.idempotency_key != mutated_envelope.idempotency_key, (
            f"{fixture['label']}: idempotency_key unchanged after {id_field!r} mutation"
        )

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_d2_create_and_cancel_idempotency_keys_differ_per_provider(
        self, provider: str
    ) -> None:
        """Each provider's CREATE and CANCEL fixtures must have different keys."""
        docs = _load_fixtures_for(provider)
        envelopes = [_run_fixture(doc) for doc in docs]
        keys = [e.idempotency_key for e in envelopes]
        assert len(keys) == len(set(keys)), (
            f"{provider}: idempotency_key collision between fixtures: {keys}"
        )


# ---------------------------------------------------------------------------
# Group E — Coverage invariant: each provider has CREATE + CANCEL
# ---------------------------------------------------------------------------

class TestGroupECoverageInvariant:

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_e1_provider_has_at_least_two_fixtures(self, provider: str) -> None:
        docs = _load_fixtures_for(provider)
        assert len(docs) >= 2, (
            f"{provider}: expected >= 2 fixtures, found {len(docs)}"
        )

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_e2_provider_has_booking_created_fixture(self, provider: str) -> None:
        docs = _load_fixtures_for(provider)
        types = [_run_fixture(d).type for d in docs]
        assert "BOOKING_CREATED" in types, (
            f"{provider}: no BOOKING_CREATED fixture found"
        )

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_e3_provider_has_booking_canceled_fixture(self, provider: str) -> None:
        docs = _load_fixtures_for(provider)
        types = [_run_fixture(d).type for d in docs]
        assert "BOOKING_CANCELED" in types, (
            f"{provider}: no BOOKING_CANCELED fixture found"
        )

    def test_e4_total_fixture_count_is_twenty_two(self) -> None:
        """Exactly 22 fixtures: 11 providers × 2 (CREATE + CANCEL)."""
        assert len(ALL_FIXTURES) == 22, (
            f"Expected 22 fixtures, found {len(ALL_FIXTURES)}: {FIXTURE_IDS}"
        )

    @pytest.mark.parametrize("provider", EXPECTED_PROVIDERS)
    def test_e5_all_fixture_labels_are_unique(self, provider: str) -> None:
        docs = _load_fixtures_for(provider)
        labels = [d["label"] for d in docs]
        assert len(labels) == len(set(labels)), (
            f"{provider}: duplicate labels found: {labels}"
        )

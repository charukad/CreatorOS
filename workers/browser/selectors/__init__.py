from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from apps.api.schemas.enums import ProviderName

_SELECTOR_ROOT = Path(__file__).with_name("versions")
_LATEST_SELECTOR_VERSIONS = {
    ProviderName.ELEVENLABS_WEB: "v1",
    ProviderName.FLOW_WEB: "v1",
}


@dataclass(frozen=True, slots=True)
class SelectorDefinition:
    key: str
    description: str
    candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelectorBundle:
    provider_name: ProviderName
    version: str
    workspace_label: str
    selectors: dict[str, SelectorDefinition]

    def selector_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.selectors))

    def candidates_for(self, key: str) -> tuple[str, ...]:
        selector = self.selectors.get(key)
        if selector is None:
            raise KeyError(f"Unknown selector key for {self.provider_name.value}: {key}")
        return selector.candidates


@dataclass(frozen=True, slots=True)
class ResolvedSelectorCandidate:
    key: str
    candidate: str
    candidate_index: int
    description: str


def get_latest_selector_version(provider_name: ProviderName) -> str:
    try:
        return _LATEST_SELECTOR_VERSIONS[provider_name]
    except KeyError as error:
        raise ValueError(
            f"No selector registry version is configured for {provider_name.value}."
        ) from error


def selector_bundle_path(provider_name: ProviderName, version: str | None = None) -> Path:
    resolved_version = version or get_latest_selector_version(provider_name)
    return _SELECTOR_ROOT / provider_name.value / f"{resolved_version}.json"


@lru_cache
def load_selector_bundle(
    provider_name: ProviderName,
    version: str | None = None,
) -> SelectorBundle:
    resolved_version = version or get_latest_selector_version(provider_name)
    path = selector_bundle_path(provider_name, resolved_version)
    if not path.exists():
        raise FileNotFoundError(f"Selector registry file is missing: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    file_provider_name = ProviderName(payload["provider_name"])
    if file_provider_name != provider_name:
        raise ValueError(
            "Selector registry provider mismatch. "
            f"Expected {provider_name.value}, found {file_provider_name.value}."
        )
    if payload["version"] != resolved_version:
        raise ValueError(
            "Selector registry version mismatch. "
            f"Expected {resolved_version}, found {payload['version']}."
        )

    raw_selectors = payload.get("selectors", {})
    selectors: dict[str, SelectorDefinition] = {}
    for key, selector_payload in raw_selectors.items():
        candidates = tuple(
            candidate.strip()
            for candidate in selector_payload.get("candidates", [])
            if candidate.strip()
        )
        if not candidates:
            raise ValueError(
                f"Selector key {key!r} in {path} must define at least one candidate selector."
            )
        selectors[key] = SelectorDefinition(
            key=key,
            description=str(selector_payload.get("description", "")).strip(),
            candidates=candidates,
        )

    if not selectors:
        raise ValueError(f"Selector registry file {path} does not define any selectors.")

    return SelectorBundle(
        provider_name=provider_name,
        version=resolved_version,
        workspace_label=str(payload.get("workspace_label", provider_name.value)),
        selectors=selectors,
    )


def selector_bundle_summary(bundle: SelectorBundle) -> dict[str, object]:
    return {
        "provider_name": bundle.provider_name.value,
        "version": bundle.version,
        "workspace_label": bundle.workspace_label,
        "selector_keys": list(bundle.selector_keys()),
        "candidate_count": sum(len(selector.candidates) for selector in bundle.selectors.values()),
    }


def resolve_selector_candidate(
    bundle: SelectorBundle,
    key: str,
    *,
    predicate: Callable[[str], bool],
) -> ResolvedSelectorCandidate:
    selector = bundle.selectors.get(key)
    if selector is None:
        raise KeyError(f"Unknown selector key for {bundle.provider_name.value}: {key}")

    for candidate_index, candidate in enumerate(selector.candidates):
        if predicate(candidate):
            return ResolvedSelectorCandidate(
                key=key,
                candidate=candidate,
                candidate_index=candidate_index,
                description=selector.description,
            )

    raise LookupError(
        f"No selector candidates matched for key {key!r} in {bundle.provider_name.value}."
    )

"""Typed contracts for Port-domain GitHub client responses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Optional, TypeVar


T = TypeVar("T")


class FetchState(str, Enum):
    """Normalized response state for downstream ingestion stages."""

    OK = "ok"
    UNCHANGED = "unchanged"
    EMPTY = "empty"
    FAILED = "failed"


@dataclass(slots=True)
class FetchResult(Generic[T]):
    """Container that separates payload from fetch semantics."""

    state: FetchState
    data: Optional[T] = None
    etag: Optional[str] = None
    status_code: Optional[int] = None
    error: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.state == FetchState.OK

    @property
    def is_unchanged(self) -> bool:
        return self.state == FetchState.UNCHANGED

    @property
    def is_empty(self) -> bool:
        return self.state == FetchState.EMPTY

    @property
    def is_failed(self) -> bool:
        return self.state == FetchState.FAILED


RepoPayload = dict[str, Any]
ReleasePayload = list[dict[str, Any]]
TagPayload = list[dict[str, Any]]
StargazerPayload = list[dict[str, Any]]
ContentPayload = str

RepoContract = FetchResult[RepoPayload]
ReleaseContract = FetchResult[ReleasePayload]
TagContract = FetchResult[TagPayload]
StargazerContract = FetchResult[StargazerPayload]
ContentContract = FetchResult[ContentPayload]

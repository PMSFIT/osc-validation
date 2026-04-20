from typing import Protocol

from .models import TriggerTransformRequest, TriggerTransformResult


class TriggerTransformer(Protocol):
    @staticmethod
    def apply(request: TriggerTransformRequest) -> TriggerTransformResult:
        ...

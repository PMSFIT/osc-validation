from typing import Protocol

from osc_validation.cases.triggers.models import (
    TriggerTransformRequest,
    TriggerTransformResult,
)


class TriggerTransformer(Protocol):
    @staticmethod
    def apply(request: TriggerTransformRequest) -> TriggerTransformResult: ...

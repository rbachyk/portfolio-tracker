from enum import StrEnum


class CostBasisMethod(StrEnum):
    FIFO = "FIFO"
    LIFO = "LIFO"
    HIFO = "HIFO"
    AVERAGE = "AVERAGE"


def ensure_supported_method(method: CostBasisMethod) -> None:
    if method != CostBasisMethod.FIFO:
        raise NotImplementedError(f"{method.value} cost basis is not implemented yet")

from typing import Any, Dict, Optional, TypedDict, Union


class WhereConditionValue(TypedDict, total=False):
    value: Any
    mode: str


class WhereConditionRange(TypedDict, total=False):
    lt: Optional[Any]
    lte: Optional[Any]
    gt: Optional[Any]
    gte: Optional[Any]


WhereCondition = Union[Any, WhereConditionValue, WhereConditionRange]


class WhereClause(TypedDict, total=False):
    OR: Optional["WhereClause"]
    __annotations__: Dict[str, WhereCondition]

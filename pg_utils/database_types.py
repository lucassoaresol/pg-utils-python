from typing import Any, Dict, Literal, Optional, TypedDict, Union


class JoinParams(TypedDict):
    table: str
    alias: Optional[str]
    on: Dict[str, str]
    type: Optional[Literal["INNER", "LEFT", "RIGHT"]]


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

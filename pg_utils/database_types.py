from typing import Any, Dict, Literal, Optional, TypedDict, Union


class JoinParams(TypedDict):
    table: str
    alias: Optional[str]
    on: Dict[str, str]
    type: Optional[Literal["INNER", "LEFT", "RIGHT"]]


class WhereConditionValue(TypedDict, total=False):
    value: Any
    mode: Optional[str]
    is_not: Optional[bool]


class WhereConditionRange(TypedDict, total=False):
    lt: Optional[Union[Any, WhereConditionValue]]
    lte: Optional[Union[Any, WhereConditionValue]]
    gt: Optional[Union[Any, WhereConditionValue]]
    gte: Optional[Union[Any, WhereConditionValue]]


WhereCondition = Union[Any, WhereConditionValue, WhereConditionRange]


class WhereClause(TypedDict, total=False):
    OR: Optional["WhereClause"]
    __annotations__: Dict[str, WhereCondition]

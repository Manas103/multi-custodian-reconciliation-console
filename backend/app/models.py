"""Typed record and break shapes shared by the fast matcher, the independent
oracle, the Lambda handler, and the AWS cost benchmark. All data here is
synthetic; see the README's honest framing section.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecordType(str, Enum):
    POSITION = "POSITION"
    CASH = "CASH"
    TRANSACTION = "TRANSACTION"


class BreakRule(str, Enum):
    TIMING = "timing"
    QUANTITY = "quantity"
    PRICE = "price"
    MISSING = "missing"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class Record:
    """One line of a daily feed: a position, a cash balance, or a
    transaction, reported by either the custodian or the internal book of
    record. `key` disambiguates rows within one (account, record_type):
    a security symbol for POSITION, the fixed string "CASH" for CASH, and a
    transaction id for TRANSACTION.
    """

    account: str
    record_type: RecordType
    key: str
    as_of_date: str  # ISO date
    quantity: float
    price: float

    def match_key(self) -> tuple[str, str, str]:
        return (self.account, self.record_type.value, self.key)


@dataclass(frozen=True)
class Break:
    account: str
    record_type: RecordType
    key: str
    rule: BreakRule
    disagreeing_field: str
    custodian_value: str | None
    book_value: str | None

    def to_dict(self) -> dict:
        return {
            "account": self.account,
            "record_type": self.record_type.value,
            "key": self.key,
            "rule": self.rule.value,
            "disagreeing_field": self.disagreeing_field,
            "custodian_value": self.custodian_value,
            "book_value": self.book_value,
        }

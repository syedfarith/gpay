from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PaymentStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentError(Exception):
    pass


@dataclass
class Payment:
    amount: float
    currency: str
    payer: str
    payee: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)


class PaymentGateway:
    def __init__(self) -> None:
        self._balances: dict[str, float] = {}
        self._payments: dict[str, Payment] = {}

    def deposit(self, account: str, amount: float) -> None:
        if amount <= 0:
            raise PaymentError("Deposit amount must be positive")
        self._balances[account] = self._balances.get(account, 0.0) + amount

    def get_balance(self, account: str) -> float:
        return self._balances.get(account, 0.0)

    def create_payment(
        self, payer: str, payee: str, amount: float, currency: str = "USD"
    ) -> Payment:
        if amount <= 0:
            raise PaymentError("Payment amount must be positive")

        payment = Payment(amount=amount, currency=currency, payer=payer, payee=payee)
        self._payments[payment.id] = payment

        if self.get_balance(payer) < amount:
            payment.status = PaymentStatus.FAILED
            raise PaymentError(f"Insufficient funds for {payer}")

        self._balances[payer] -= amount
        self._balances[payee] = self._balances.get(payee, 0.0) + amount
        payment.status = PaymentStatus.SUCCESS
        return payment

    def refund(self, payment_id: str) -> Payment:
        payment = self._payments.get(payment_id)
        if payment is None:
            raise PaymentError(f"Payment {payment_id} not found")
        if payment.status != PaymentStatus.SUCCESS:
            raise PaymentError(f"Payment {payment_id} cannot be refunded")

        self._balances[payment.payee] -= payment.amount
        self._balances[payment.payer] = (
            self._balances.get(payment.payer, 0.0) + payment.amount
        )
        payment.status = PaymentStatus.REFUNDED
        return payment

    def get_payment(self, payment_id: str) -> Payment:
        payment = self._payments.get(payment_id)
        if payment is None:
            raise PaymentError(f"Payment {payment_id} not found")
        return payment


def main() -> None:
    gateway = PaymentGateway()
    gateway.deposit("alice", 100.0)

    print(f"Alice balance: {gateway.get_balance('alice')}")

    payment = gateway.create_payment(payer="alice", payee="bob", amount=25.0)
    print(f"Payment {payment.id} status: {payment.status.value}")
    print(f"Alice balance: {gateway.get_balance('alice')}")
    print(f"Bob balance: {gateway.get_balance('bob')}")

    gateway.refund(payment.id)
    print(f"After refund - Alice: {gateway.get_balance('alice')}, Bob: {gateway.get_balance('bob')}")


if __name__ == "__main__":
    main()

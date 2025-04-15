import datetime
import uuid
from decimal import Decimal
from enum import Enum
from typing import Protocol, List, Optional

# --- Core Data Models ---

class AccountType(Enum):
    CHECKING = "Checking"
    SAVINGS = "Savings"

class TransactionType(Enum):
    CREDIT = "Credit"
    DEBIT = "Debit"

class ACHTransactionStatus(Enum):
    INITIATED = "Initiated"
    PENDING = "Pending"
    POSTED = "Posted"
    RETURNED = "Returned"
    FAILED = "Failed"
    REVERSED = "Reversed"

class ReturnCode(Enum):
    R01 = "Insufficient Funds"
    R02 = "Account Closed"
    R03 = "No Account/Unable to Locate Account"
    # ... Add other return codes as needed

class ACHTransaction:
    def __init__(self, originator_account_id: str, receiver_account_id: str, amount: Decimal,
                 transaction_type: TransactionType, account_type: AccountType,
                 effective_date: datetime.date, description: str, company_id: str,
                 standard_entry_class: str, transaction_id: Optional[str] = None,
                 status: ACHTransactionStatus    = ACHTransactionStatus.INITIATED,
                 return_code: Optional[ReturnCode] = None, return_reason: Optional[str] = None,
                 created_at: Optional[datetime.datetime] = None,
                 updated_at: Optional[datetime.datetime] = None):
        self.transaction_id = transaction_id or str(uuid.uuid4())
        self.originator_account_id = originator_account_id
        self.receiver_account_id = receiver_account_id
        self.amount = Decimal(amount)
        self.transaction_type = transaction_type
        self.account_type = account_type
        self.effective_date = effective_date
        self.description = description
        self.company_id = company_id
        self.standard_entry_class = standard_entry_class
        self.status = status
        self.return_code = return_code
        self.return_reason = return_reason
        self.created_at = created_at or datetime.datetime.utcnow()
        self.updated_at = updated_at or datetime.datetime.utcnow()

    def __repr__(self):
        return f"ACHTransaction(id={self.transaction_id}, amount={self.amount}, status={self.status})"

class Account:
    def __init__(self, account_number: str, routing_number: str, account_type: AccountType,
                 user_id: str, account_id: Optional[str] = None, balance: Decimal = Decimal(0)):
        self.account_id = account_id or str(uuid.uuid4())
        self.account_number = account_number
        self.routing_number = routing_number
        self.account_type = account_type
        self.user_id = user_id
        self.balance = Decimal(balance)

# --- Database Interface (Protocol) ---

class Database(Protocol):
    def save_transaction(self, transaction: ACHTransaction) -> None: ...
    def get_transaction(self, transaction_id: str) -> Optional[ACHTransaction]: ...
    def get_transactions_by_status(self, status: ACHTransactionStatus) -> List[ACHTransaction]: ...
    def update_transaction(self, transaction: ACHTransaction) -> None: ...
    def save_account(self, account: Account) -> None: ...
    def get_account(self, account_id: str) -> Optional[Account]: ...
    def update_account(self, account: Account) -> None: ...

# --- ACH Processing Logic ---

class ACHProcessor:
    def __init__(self, database: Database):
        self.database = database

    def initiate_transaction(self, originator_account_id: str, receiver_account_id: str,
                             amount: Decimal, transaction_type: TransactionType,
                             account_type: AccountType, effective_date: datetime.date,
                             description: str, company_id: str, standard_entry_class: str) -> ACHTransaction:
        transaction = ACHTransaction(originator_account_id, receiver_account_id, amount,
                                     transaction_type, account_type, effective_date,
                                     description, company_id, standard_entry_class)
        self.database.save_transaction(transaction)
        return transaction

    def process_pending_transactions(self) -> None:
        pending_transactions = self.database.get_transactions_by_status(ACHTransactionStatus.PENDING)
        for transaction in pending_transactions:
            if transaction.effective_date <= datetime.date.today():
                self.post_transaction(transaction)

    def post_transaction(self, transaction: ACHTransaction) -> None:
        originator_account = self.database.get_account(transaction.originator_account_id)
        receiver_account = self.database.get_account(transaction.receiver_account_id)

        if originator_account is None or receiver_account is None:
            transaction.status = ACHTransactionStatus.FAILED
            transaction.return_code = ReturnCode.R03
            transaction.return_reason = "Originator or Receiver account not found"
            self.database.update_transaction(transaction)
            return

        if transaction.transaction_type == TransactionType.DEBIT:
            if originator_account.balance < transaction.amount:
                transaction.status = ACHTransactionStatus.RETURNED
                transaction.return_code = ReturnCode.R01
                transaction.return_reason = "Insufficient funds"
                self.database.update_transaction(transaction)
                return
            originator_account.balance -= transaction.amount
            receiver_account.balance += transaction.amount
        else:  # credit
            receiver_account.balance += transaction.amount

        transaction.status = ACHTransactionStatus.POSTED
        self.database.update_account(originator_account)
        self.database.update_account(receiver_account)
        self.database.update_transaction(transaction)

    def handle_return(self, transaction_id: str, return_code: ReturnCode, return_reason: str) -> None:
        transaction = self.database.get_transaction(transaction_id)
        if transaction is None:
            return

        transaction.status = ACHTransactionStatus.RETURNED
        transaction.return_code = return_code
        transaction.return_reason = return_reason
        self.database.update_transaction(transaction)

    def reverse_transaction(self, transaction_id: str) -> None:
        transaction = self.database.get_transaction(transaction_id)
        if transaction is None or transaction.status != ACHTransactionStatus.POSTED:
            return

        originator_account = self.database.get_account(transaction.originator_account_id)
        receiver_account = self.database.get_account(transaction.receiver_account_id)

        if transaction.transaction_type == TransactionType.DEBIT:
            originator_account.balance += transaction.amount
            receiver_account.balance -= transaction.amount
        else:
            receiver_account.balance -= transaction.amount
            originator_account.balance += transaction.amount

        transaction.status = ACHTransactionStatus.REVERSED
        self.database.update_account(originator_account)
        self.database.update_account(receiver_account)
        self.database.update_transaction(transaction)

# --- In-Memory Database Implementation ---

class InMemoryDatabase:
    def __init__(self):
        self.transactions = {}
        self.accounts = {}

    def save_transaction(self, transaction: ACHTransaction) -> None:
        self.transactions[transaction.transaction_id] = transaction

    def get_transaction(self, transaction_id: str) -> Optional[ACHTransaction]:
        return self.transactions.get(transaction_id)

    def get_transactions_by_status(self, status: ACHTransactionStatus) -> List[ACHTransaction]:
        return [t for t in self.transactions.values() if t.status == status]

    def update_transaction(self, transaction: ACHTransaction) -> None:
        self.transactions[transaction.transaction_id] = transaction

    def save_account(self, account: Account) -> None:
        self.accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Optional[Account]:
        return self.accounts.get(account_id)

    def update_account(self, account: Account) -> None:
        self.accounts[account.account_id] = account
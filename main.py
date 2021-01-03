import csv
import glob
import json
import math
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from os import path


class Transaction:
    posted: date
    amount: Decimal

    def __init__(self, posted: date, amount: Decimal):
        self.posted = posted
        self.amount = amount


class Account:
    name: str
    split: bool
    txns: list[Transaction]

    def __init__(self, filename: str, profile: dict):
        if not filename.endswith('.ally.csv'):
            raise RuntimeError

        with open(filename, newline='') as file:
            reader = csv.reader(file, skipinitialspace=True)
            next(reader)
            self.txns = list([Transaction(date.fromisoformat(row[0]), Decimal(row[2]))
                              for row in reader])

        filename = path.basename(filename)
        self.name = filename
        self.split = filename in profile['split_accounts']

    def __str__(self):
        return self.name + (' (split)' if self.split else '')

    __repr__ = __str__


class FixedExpense:
    name: str
    split: bool
    amount: Decimal

    def __init__(self, name: str, info: dict):
        self.name = name
        self.split = info.get('split') or False
        self.amount = Decimal(info['amount'])

    def __str__(self):
        return '%s: $%.02f' % (self.name, self.amount.__float__())

    __repr__ = __str__


class VariableExpense:
    name: str
    split: bool
    txns: list[Transaction]

    def __init__(self, filename: str, profile: dict):
        if not filename.endswith('.csv'):
            raise RuntimeError

        with open(filename, newline='') as file:
            reader = csv.reader(file, skipinitialspace=True)
            self.txns = list([Transaction(date.fromisoformat(row[0]), Decimal(row[1]))
                              for row in reader])

        filename = path.basename(filename)
        self.name = filename
        self.split = filename in profile['split_variable_expenses']

    def __str__(self):
        return '%s: $%.02f' % (self.name, self.txns[-1].amount.__float__())

    __repr__ = __str__


def in_same_month(a: date, b: date) -> bool:
    return a.year == b.year and a.month == b.month


def round_money(amount):
    return math.ceil(amount * 100) / 100


def minus_months(d: date, n: int = 1) -> date:
    for _ in range(n):
        d = d.replace(day=1) - timedelta(days=1)
    return d


def in_past_months(start: date, n: int, d: date) -> bool:
    to_check = start.replace(day=1)
    for _ in range(n):
        to_check -= timedelta(days=1)
        to_check = to_check.replace(day=1)

        if in_same_month(d, to_check):
            return True

    return False


def main():
    with open('profile.json') as file:
        profile = json.load(file)

    accounts = [Account(filename, profile)
                for filename in glob.glob('accounts/*[!.example].csv')]

    fixed_expenses = [FixedExpense(name, info)
                      for name, info in profile['fixed_expenses'].items()]

    variable_expenses = [VariableExpense(filename, profile)
                         for filename in glob.glob('variable_expenses/*[!.example].csv')]

    due_mo = datetime.strptime(sys.argv[1], '%m/%y')
    prev_mo = minus_months(due_mo)
    split_due = 0
    solo_due = 0

    for expense in fixed_expenses:
        if expense.split:
            split_due += expense.amount / 2
        else:
            solo_due += expense.amount

    for expense in variable_expenses:
        amount = [txn.amount for txn in expense.txns if in_same_month(txn.posted, prev_mo)][-1] / 2
        if expense.split:
            split_due += amount / 2
        else:
            solo_due += amount

    split_in = 0
    split_out = 0
    solo_in = 0
    solo_out = 0

    for account in accounts:
        amount_in = sum([txn.amount
                         for txn in account.txns
                         if txn.amount > 0 and in_same_month(txn.posted, prev_mo)])
        amount_out = sum([txn.amount
                          for txn in account.txns
                          if txn.amount < 0 and in_same_month(txn.posted, prev_mo)])
        if account.split:
            split_in += amount_in / 2
            split_out += amount_out / 2
        else:
            solo_in += amount_in
            solo_out += amount_out

    est_out = -sum([sum([txn.amount / 2 if account.split else txn.amount
                         for txn in account.txns
                         if in_past_months(due_mo, 3, txn.posted)])
                    for account in accounts]) / 3

    net_due = split_due + solo_due + est_out
    net_in_out = split_in + split_out + solo_in + solo_out

    print('Due {:%B %Y}:'.format(due_mo))
    print()
    print(' Personal ${:>10.2f}'.format(round_money(solo_due)))
    print('    Joint ${:>10.2f}'.format(round_money(split_due)))
    print('Estimated ${:>10.2f}'.format(round_money(est_out)))
    print('          -----------')
    print('          ${:>10.2f}'.format(round_money(net_due)))
    print()
    print('Cash flow for {:%B %Y}:'.format(prev_mo))
    print()
    print('Personal (+) ${:>10.2f}'.format(round_money(solo_in)))
    print('   Joint (+) ${:>10.2f}'.format(round_money(split_in)))
    print('Personal (-) ${:>10.2f}'.format(round_money(solo_out)))
    print('   Joint (-) ${:>10.2f}'.format(round_money(split_out)))
    print('             -----------')
    print('             ${:>10.2f}'.format(round_money(net_in_out)))


if __name__ == '__main__':
    main()

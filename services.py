from __future__ import annotations
import datetime
from typing import Optional

import model
from model import OrderLine
from repository import AbstractRepository


class InvalidSku(Exception):
    pass


def is_valid_sku(sku, batches):
    return sku in {b.sku for b in batches}


def allocate(line: OrderLine, repo: AbstractRepository, session) -> str:
    batches = repo.list()
    if not is_valid_sku(line.sku, batches):
        raise InvalidSku(f"Invalid sku {line.sku}")
    batchref = model.allocate(line, batches)
    session.commit()
    return batchref

def deallocate(order_id:str, sku:str, repo:AbstractRepository,session):

    order_line = repo.get_line_item(order_id, sku)
    
    if not order_line :
        raise Exception("Couldnt find the order line")

    batches = repo.list()

    for batch in batches:
        if order_line in batch._allocations:
            batch.deallocate(order_line)
            break
    else:
        raise Exception("Couldnt find the order line in any batch")

    session.commit()


def add_batch(ref:str, sku:str, qty:int, eta:Optional[datetime.date], repo:AbstractRepository, session):
    repo.add(model.Batch(ref, sku, qty, eta))
    session.commit()
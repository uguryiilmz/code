from datetime import date

import pytest
import model
import repository
import services


class FakeRepository(repository.AbstractRepository):
    def __init__(self, batches):
        self._batches = set(batches)

    def add(self, batch):
        self._batches.add(batch)

    def get(self, reference):
        return next(b for b in self._batches if b.reference == reference)

    def list(self):
        return list(self._batches)
    
    def get_line_item(self, order_id, sku):
        for batch in self._batches:
            for line in batch._allocations:
                if line.orderid == order_id and line.sku == sku:
                    return line
        return None


class FakeSession:
    committed = False

    def commit(self):
        self.committed = True


def test_returns_allocation():
    line = model.OrderLine("o1", "COMPLICATED-LAMP", 10)
    batch = model.Batch("b1", "COMPLICATED-LAMP", 100, eta=None)
    repo = FakeRepository([batch])

    result = services.allocate(line, repo, FakeSession())
    assert result == "b1"


def test_error_for_invalid_sku():
    line = model.OrderLine("o1", "NONEXISTENTSKU", 10)
    batch = model.Batch("b1", "AREALSKU", 100, eta=None)
    repo = FakeRepository([batch])

    with pytest.raises(services.InvalidSku, match="Invalid sku NONEXISTENTSKU"):
        services.allocate(line, repo, FakeSession())


def test_commits():
    line = model.OrderLine("o1", "OMINOUS-MIRROR", 10)
    batch = model.Batch("b1", "OMINOUS-MIRROR", 100, eta=None)
    repo = FakeRepository([batch])
    session = FakeSession()

    services.allocate(line, repo, session)
    assert session.committed is True


def test_deallocate_decrements_available_quantity():
    repo, session = FakeRepository([]), FakeSession()
    # TODO: you'll need to implement the services.add_batch method
    services.add_batch("b1", "BLUE-PLINTH", 100, None, repo, session)
    line = model.OrderLine("o1", "BLUE-PLINTH", 10)
    services.allocate(line, repo, session)
    batch = repo.get(reference="b1")
    assert batch.available_quantity == 90
    services.deallocate(line.orderid, line.sku, repo, session)

    assert batch.available_quantity == 100


def test_deallocate_decrements_correct_quantity():
    """Among batches with the same SKU, earliest ETA wins; deallocate must target that batch."""
    repo, session = FakeRepository([]), FakeSession()
    services.add_batch("b1", "BLUE-PLINTH", 100, date(2011, 1, 1), repo, session)
    services.add_batch("b2", "BLUE-PLINTH", 100, date(2011, 1, 2), repo, session)
    services.add_batch("b3", "RED-PLINTH", 100, None, repo, session)
    line = model.OrderLine("o1", "BLUE-PLINTH", 10)
    services.allocate(line, repo, session)
    batch_b1 = repo.get(reference="b1")
    assert batch_b1.available_quantity == 90
    services.deallocate(line.orderid, line.sku, repo, session)

    assert batch_b1.available_quantity == 100


def test_deallocate_needs_sku_when_one_order_has_several_line_items():

    repo, session = FakeRepository([]), FakeSession()
    services.add_batch("b-blue", "BLUE-PLINTH", 100, None, repo, session)
    services.add_batch("b-red", "RED-PLINTH", 100, None, repo, session)

    orderid = "ORD-MULTI"
    line_blue = model.OrderLine(orderid, "BLUE-PLINTH", 10)
    line_red = model.OrderLine(orderid, "RED-PLINTH", 7)

    services.allocate(line_blue, repo, session)
    services.allocate(line_red, repo, session)

    batch_blue = repo.get(reference="b-blue")
    batch_red = repo.get(reference="b-red")
    assert batch_blue.available_quantity == 90
    assert batch_red.available_quantity == 93

    services.deallocate(orderid, "BLUE-PLINTH", repo, session)

    assert batch_blue.available_quantity == 100
    assert batch_red.available_quantity == 93


def test_trying_to_deallocate_unallocated_batch():
    """Deallocate fails when order line is not allocated to any batch."""
    repo, session = FakeRepository([]), FakeSession()
    services.add_batch("b1", "BLUE-PLINTH", 100, None, repo, session)
    line = model.OrderLine("o1", "BLUE-PLINTH", 10)
    with pytest.raises(Exception, match="Couldnt find the order line"):
        services.deallocate(line.orderid, line.sku, repo, session)
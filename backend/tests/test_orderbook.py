"""Order book correctness — the money path. Run: pytest backend/tests -q"""
from app.engine.market import Order, Side
from app.engine.orderbook import OrderBook


def buy(px, qty, who="t"):
    return Order("X", Side.BUY, qty, px, who)


def sell(px, qty, who="t"):
    return Order("X", Side.SELL, qty, px, who)


def test_no_cross_rests():
    b = OrderBook("X")
    assert b.add(buy(100, 10)) == []
    assert b.add(sell(101, 10)) == []
    assert b.best_bid() == 100 and b.best_ask() == 101
    assert b.spread() == 1


def test_full_fill_at_resting_price():
    b = OrderBook("X")
    b.add(sell(101, 10, "maker"))
    trades = b.add(buy(101, 10, "taker"))  # aggressor buys into resting ask
    assert len(trades) == 1
    t = trades[0]
    assert t.price == 101 and t.qty == 10
    assert t.buy_trader_id == "taker" and t.sell_trader_id == "maker"
    assert t.aggressor is Side.BUY
    assert b.best_ask() is None  # ask consumed


def test_partial_fill_leaves_residual():
    b = OrderBook("X")
    b.add(sell(101, 4, "maker"))
    trades = b.add(buy(101, 10, "taker"))
    assert sum(t.qty for t in trades) == 4
    assert b.best_bid() == 101  # 6 residual rests as a bid
    assert b.depth()["bids"][0] == (101, 6)


def test_price_time_priority():
    b = OrderBook("X")
    b.add(sell(101, 5, "first"))
    b.add(sell(101, 5, "second"))
    trades = b.add(buy(101, 5, "taker"))  # must hit FIFO -> "first"
    assert trades[0].sell_trader_id == "first"
    trades = b.add(buy(101, 5, "taker"))
    assert trades[0].sell_trader_id == "second"


def test_buy_takes_cheapest_ask_first():
    b = OrderBook("X")
    b.add(sell(103, 5, "high"))
    b.add(sell(101, 5, "low"))
    trades = b.add(buy(103, 5, "taker"))
    assert trades[0].price == 101 and trades[0].sell_trader_id == "low"


def test_market_order_sweeps_levels():
    b = OrderBook("X")
    b.add(sell(101, 5, "a"))
    b.add(sell(102, 5, "b"))
    trades = b.add(Order("X", Side.BUY, 8, None, "taker"))  # market buy 8
    assert sum(t.qty for t in trades) == 8
    assert [t.price for t in trades] == [101, 102]
    assert b.best_ask() == 102 and b.depth()["asks"][0] == (102, 2)


def test_cancel_removes_order():
    b = OrderBook("X")
    o = buy(100, 10)
    b.add(o)
    assert b.cancel(o.id) is True
    assert b.best_bid() is None
    assert b.cancel(o.id) is False  # already gone


def test_book_invariant_bid_below_ask():
    b = OrderBook("X")
    b.add(buy(100, 10))
    b.add(sell(101, 10))
    assert b.best_bid() < b.best_ask()

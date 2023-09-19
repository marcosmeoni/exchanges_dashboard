from sqlalchemy import UniqueConstraint, PrimaryKeyConstraint, Column, Integer, DateTime, func, String, Float, Boolean, \
    ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

_DECL_BASE = declarative_base()


class OrderEntity(_DECL_BASE):
    __tablename__ = 'ORDERS'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer)
    registration_datetime = Column(DateTime, default=func.now())
    type = Column(String(255))
    symbol = Column(String(255))
    quantity = Column(Float)
    side = Column(String(255))
    position_side = Column(String(255))
    status = Column(String(255))
    price = Column(Float)
    stop_price = Column(Float)
    timeInForce = Column(String(255))
    activation_price = Column(Float)
    callback_rate = Column(Float)
    close_position = Column(Boolean)
    account = Column(String(255))


class DailyBalanceEntity(_DECL_BASE):
    __tablename__ = 'DAILY_BALANCE'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    day = Column(DateTime)
    totalWalletBalance = Column(Float)
    account = Column(String(255))


class BalanceEntity(_DECL_BASE):
    __tablename__ = 'BALANCE'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    totalWalletBalance = Column(Float)
    totalUnrealizedProfit = Column(Float)
    account = Column(String(255))
    assets = relationship("AssetBalanceEntity",
                          back_populates="balance", cascade="all, delete")


class AssetBalanceEntity(_DECL_BASE):
    __tablename__ = 'ASSET_BALANCE'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    asset = Column(String(255))
    walletBalance = Column(Float)
    unrealizedProfit = Column(Float)
    balance_id = Column(Integer, ForeignKey('BALANCE.id'))
    balance = relationship("BalanceEntity", back_populates="assets")
    account = Column(String(255))


class PositionEntity(_DECL_BASE):
    __tablename__ = 'POSITION'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    symbol = Column(String(255))
    side = Column(String(255))
    unrealizedProfit = Column(Float)
    entryPrice = Column(Float)
    quantity = Column(Float)
    initialMargin = Column(Float)
    account = Column(String(255))


class CurrentPriceEntity(_DECL_BASE):
    __tablename__ = 'PRICE'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    symbol = Column(String(255))
    price = Column(Float)
    account = Column(String(255))


class IncomeEntity(_DECL_BASE):
    __tablename__ = 'INCOME'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    transaction_id = Column(Integer, nullable=False, unique=True)
    symbol = Column(String(255))
    incomeType = Column(String(255))
    income = Column(Float)
    asset = Column(String(255))
    time = Column(DateTime)
    timestamp = Column(Integer)
    account = Column(String(255))

    __table_args__ = (
        UniqueConstraint('transaction_id'),
    )


class TradeEntity(_DECL_BASE):
    __tablename__ = 'Trade'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    order_id = Column(Integer, nullable=False, unique=True)
    symbol = Column(String(255))
    incomeType = Column(String(255))
    asset = Column(String(255))
    quantity = Column(Float)
    price = Column(Float)
    side = Column(String(255))
    time = Column(DateTime)
    timestamp = Column(Integer)
    account = Column(String(255))

    __table_args__ = (
        UniqueConstraint('order_id'),
    )


class TradedSymbolEntity(_DECL_BASE):
    __tablename__ = 'TRADED_SYMBOL'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    symbol = Column(String(255), unique=True, nullable=False)
    last_trades_downloaded = Column(DateTime)
    account = Column(String(255))


class SymbolCheckEntity(_DECL_BASE):
    __tablename__ = 'CHECKED_SYMBOL'
    id = Column(Integer, primary_key=True)
    registration_datetime = Column(DateTime, default=func.now())
    symbol = Column(String(255), unique=True, nullable=False)
    last_checked_datetime = Column(DateTime, default=func.now())
    account = Column(String(255))

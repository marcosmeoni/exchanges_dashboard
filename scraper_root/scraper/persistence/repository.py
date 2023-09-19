import logging
import os
import threading
import time
import tempfile
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict

from sqlalchemy import create_engine, func, Table, asc, nulls_first, text
from sqlalchemy.orm import sessionmaker

from scraper_root.scraper.data_classes import Order, Tick, Position, Balance, Income, Trade
from scraper_root.scraper.persistence.lockable_session import LockableSession
from scraper_root.scraper.persistence.orm_classes import _DECL_BASE, CurrentPriceEntity, \
    BalanceEntity, AssetBalanceEntity, PositionEntity, IncomeEntity, OrderEntity, DailyBalanceEntity, TradeEntity, \
    TradedSymbolEntity, SymbolCheckEntity

logger = logging.getLogger(__name__)




CERTIFICATE_CONTENT = """
-----BEGIN CERTIFICATE-----
MIIDUDCCAjigAwIBAgIJAKpa7L30Su3kMA0GCSqGSIb3DQEBCwUAMDcxEzARBgNV
BAMMCmxpbm9kZS5jb20xEzARBgNVBAoMCkxpbm9kZSBMTEMxCzAJBgNVBAYTAlVT
MCAXDTIzMDkxODE4MzUwM1oYDzIwNzIxMjI5MTgzNTAzWjA3MRMwEQYDVQQDDAps
aW5vZGUuY29tMRMwEQYDVQQKDApMaW5vZGUgTExDMQswCQYDVQQGEwJVUzCCASIw
DQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALU/QtOamIXXin8dprJKO1KVzLZ0
8M/1RxMdaCvbpv5eFenXL66U6M5nsjUnHiB0JYutUPLDwN/V04b8O5Ttc+ndelOi
LIG/MoTK57fxG73JLeEuHiVMvOeybKSb0YIAXrqrLZzd6jUqz3DFUkHbDuBKXMt1
PhIuI8C1Pp3WaQoPRX4Elpdu2zp5tUqaHQtqKh/+5cqr3J3MHVBqERR132wKDAPg
RgvUMAn1cPWsHFK70JAvpxWU9EYiFc39Pw5KgiUa4iNCZ2hWq19LXlKUbD+zSaUC
92Qho7NlETCk3eDdvDe67sPXK6xhtJvrFSzgJxSUHLfrGaQW3vfAXWjAXocCAwEA
AaNdMFswDAYDVR0TBAUwAwEB/zALBgNVHQ8EBAMCAQYwHQYDVR0OBBYEFN03yQYY
3R5qrLuxEorhbYp2QHb6MB8GA1UdIwQYMBaAFN03yQYY3R5qrLuxEorhbYp2QHb6
MA0GCSqGSIb3DQEBCwUAA4IBAQBJmFGsIlEIu5/iI1Ktg887ej6gJmwnojRWCyUb
Pke4RdZJ4VGEKuLkgTiNyj7act+sg0FWOrm8uvDx2D1uDhEkwSB5nY06gGUBQMjQ
Rgrex6W/5QbjJNoYnHTodCO38jMWBkEJttskCSPA+bLvkzRLyKbaGwrxZw2BHHgd
V3csnN7H6qjO2OS9zFnWNWySAmFXirgx5R3v25Z1cKACRiqSs0wTKcHtC/3NNYew
sduzXZLKrc6Rkd7ivbUjH0npJo6y+OkVIKFe51TibDlXs5NM9OGsjld5xziE/Trr
b+AA88bEVlSXl3Nq+hgD64WY8V/jzYZGtMP9l4ylxLU378Po
-----END CERTIFICATE-----
"""

cert_file = tempfile.NamedTemporaryFile(delete=False)
cert_file.write(CERTIFICATE_CONTENT.encode())
cert_file.close()

class Repository:
    def __init__(self, accounts: List[str]):
        # Paso 1: Conexión al servidor sin especificar una base de datos
        connection_url = (
                f"mysql+pymysql://linroot:uKQORbgnUy7-EYrY@lin-28781-15425-mysql-primary.servers.linodedb.net:3306"
                f"?ssl_ca={cert_file.name}"
                )
        engine = create_engine(connection_url, echo=False)
        connection = engine.connect()

        # Paso 2: Verifica si la base de datos existe
        result = connection.execute(text("SHOW DATABASES LIKE 'exchanges_db'"))
        db_exists = result.first() is not None

        # Paso 3: Si no existe, crea la base de datos
        if not db_exists:
            connection.execute(text("CREATE DATABASE exchanges_db"))

        connection.close()
        default_url = (
                f"mysql+pymysql://linroot:uKQORbgnUy7-EYrY@lin-28781-15425-mysql-primary.servers.linodedb.net:3306/exchanges_db"
                f"?ssl_ca={cert_file.name}"
                )
        database_url = os.getenv('DATABASE_URL', default_url)

        self.engine = create_engine(database_url, echo=False)
        _DECL_BASE.metadata.create_all(self.engine)

        self.lockable_session = LockableSession(self.engine)
        self.accounts: List[str] = accounts

        update_daily_balance_thread = threading.Thread(
            name=f'sync_balance_thread', target=self.update_daily_balance, args=(accounts, ), daemon=True)
        update_daily_balance_thread.start()

    def update_daily_balance(self, accounts: List[str]):
        while True:
            with self.lockable_session as session:
                try:
                    for account in accounts:
                        session.query(DailyBalanceEntity).filter(DailyBalanceEntity.account == account).delete()
                        session.commit()
                        result = session.query(BalanceEntity.totalWalletBalance) \
                            .filter(BalanceEntity.account == account).first()
                        current_balance = 0
                        if result is not None:
                            current_balance = result[0]

                        daily_balances = []
                        with self.engine.connect() as con:
                            oldest_income = self.get_oldest_income(account=account)
                            if oldest_income is not None:
                                day = oldest_income.time.date()
                                end_date = date.today()
                                while day <= end_date:
                                    rs = con.execute(
                                        f'SELECT sum(INCOME.income) AS "sum" FROM INCOME '
                                        f'WHERE INCOME.time >= date(\'{day.strftime("%Y-%m-%d")}\') '
                                        f'AND Income.account = \'{account}\'')
                                    for row in rs:
                                        if row[0] is None:
                                            income = 0
                                        else:
                                            income = float(row[0])
                                        daily_balance = DailyBalanceEntity()
                                        daily_balance.day = day
                                        daily_balance.totalWalletBalance = current_balance - income
                                        daily_balance.account = account
                                        daily_balances.append(daily_balance)

                                    day += timedelta(days=1)

                        [session.add(balance) for balance in daily_balances]
                    session.commit()
                    logger.info('Updated daily balances')
                except Exception as e:
                    logger.error(f'Failed to update daily balance: {e}')

            time.sleep(60)

    def process_order_update(self, order: Order):
        # if order is already in the database, update it
        # if order is not in the database, insert it
        pass

    def process_tick(self, tick: Tick, account: str):
        with self.lockable_session as session:
            # find entry in database
            query = session.query(CurrentPriceEntity)
            query = query.filter(CurrentPriceEntity.symbol == tick.symbol).filter(CurrentPriceEntity.account == account)
            currentEntity = query.first()
            if currentEntity is None:
                currentEntity = CurrentPriceEntity()
                session.add(currentEntity)

            currentEntity.symbol = tick.symbol
            currentEntity.price = tick.price
            currentEntity.registration_datetime = func.now()
            currentEntity.account = account
            session.commit()
            logger.debug(f'Tick processed: {tick}')

    def get_current_price(self, symbol: str, account: str) -> CurrentPriceEntity:
        with self.lockable_session as session:
            return session.query(CurrentPriceEntity).filter(CurrentPriceEntity.symbol == symbol) \
                .filter(CurrentPriceEntity.account == account).first()

    def process_balances(self, balance: Balance, account: str):
        with self.lockable_session as session:
            logger.debug('Updating balances')
            session.query(AssetBalanceEntity).filter(AssetBalanceEntity.account == account).delete()
            session.query(BalanceEntity).filter(BalanceEntity.account == account).delete()
            session.commit()

            balanceEntity = BalanceEntity()
            balanceEntity.totalWalletBalance = balance.totalBalance
            balanceEntity.totalUnrealizedProfit = balance.totalUnrealizedProfit
            balanceEntity.account = account

            asset_balance_entities = []
            for asset in balance.assets:
                asset_balance_entity = AssetBalanceEntity()
                asset_balance_entity.asset = asset.asset
                asset_balance_entity.walletBalance = asset.balance
                asset_balance_entity.unrealizedProfit = asset.unrealizedProfit
                asset_balance_entity.account = account
                asset_balance_entities.append(asset_balance_entity)
            balanceEntity.assets = asset_balance_entities
            session.add(balanceEntity)
            session.commit()

    def process_positions(self, positions: List[Position], account: str):
        with self.lockable_session as session:
            logger.debug('Updating positions')
            session.query(PositionEntity).filter(PositionEntity.account == account).delete()

            for position in positions:
                position_entity = PositionEntity()
                position_entity.symbol = position.symbol
                position_entity.side = position.side
                position_entity.quantity = position.position_size
                position_entity.entryPrice = position.entry_price
                position_entity.unrealizedProfit = position.unrealizedProfit
                position_entity.initialMargin = position.initial_margin
                position_entity.account = account
                session.add(position_entity)
            session.commit()

    def get_oldest_trade(self, symbol: str, account: str) -> TradeEntity:
        with self.lockable_session as session:
            logger.debug('Getting oldest trade')
            result = session.query(TradeEntity).filter(TradeEntity.symbol == symbol) \
                .filter(TradeEntity.account == account).order_by(TradeEntity.time.asc()).first()
            return result

    def get_trades(self, symbol: str, account: str) -> List[TradeEntity]:
        with self.lockable_session as session:
            logger.debug(f'Getting all trades for {symbol}')
            result = session.query(TradeEntity).filter(TradeEntity.symbol == symbol) \
                .filter(TradeEntity.account == account).all()
            return result

    def get_trades_by_asset(self, asset: str, account: str) -> TradeEntity:
        with self.lockable_session as session:
            logger.debug(f'Getting all trades for asset {asset}')
            result = session.query(TradeEntity).filter(TradeEntity.symbol.like(f'{asset}%')) \
                .filter(
                TradeEntity.account == account).all()
            return result

    def get_newest_trade(self, symbol: str, account: str) -> TradeEntity:
        with self.lockable_session as session:
            logger.debug('Getting newest trade')
            result = session.query(TradeEntity).filter(TradeEntity.symbol == symbol) \
                .filter(TradeEntity.account == account).order_by(TradeEntity.time.desc()).first()
            return result

    def get_oldest_income(self, account: str) -> IncomeEntity:
        with self.lockable_session as session:
            logger.debug('Getting oldest income')
            result = session.query(IncomeEntity).filter(IncomeEntity.account == account).order_by(
                IncomeEntity.time.asc()).first()
            return result

    def get_newest_income(self, account: str) -> IncomeEntity:
        with self.lockable_session as session:
            logger.debug('Getting newest income')
            result = session.query(IncomeEntity).filter(IncomeEntity.account == account).order_by(
                IncomeEntity.time.desc()).first()
            return result
      
    def process_incomes(self, incomes: List[Income], account: str):
        if len(incomes) == 0:
            return
        with self.lockable_session as session:
            logger.warning(f'{account}: Processing incomes')
            
            # Construir la consulta con INSERT IGNORE
            query = f"""
            INSERT IGNORE INTO {IncomeEntity.__tablename__} 
            (transaction_id, symbol, incomeType, income, asset, time, timestamp, account)
            VALUES :values
            """
            
            # Crear los valores para la inserción masiva
            values = [{
                "transaction_id": income.transaction_id,
                "symbol": income.symbol,
                "incomeType": income.type,
                "income": income.income,
                "asset": income.asset,
                "time": datetime.utcfromtimestamp(income.timestamp / 1000),
                "timestamp": income.timestamp,
                "account": account
            } for income in incomes]
            
            session.execute(query, {"values": values})
            session.commit()

    # def process_incomes(self, incomes: List[Income], account: str):
    #     if len(incomes) == 0:
    #         return
    #     with self.lockable_session as session:
    #         logger.warning(f'{account}: Processing incomes')

    #         session.execute(
    #             IncomeEntity.__table__.insert(),
    #             params=[{
    #                 "transaction_id": income.transaction_id,
    #                 "symbol": income.symbol,
    #                 "incomeType": income.type,
    #                 "income": income.income,
    #                 "asset": income.asset,
    #                 "time": datetime.utcfromtimestamp(income.timestamp / 1000),
    #                 "timestamp": income.timestamp,
    #                 "account": account}
    #                 for income in incomes],
    #         )
    #         session.commit()

    def process_trades(self, trades: List[Trade], account: str):
        if len(trades) == 0:
            return
        with self.lockable_session as session:
            logger.warning('Processing trades')

            session.execute(
                TradeEntity.__table__.insert(),
                params=[{
                    "order_id": trade.order_id,
                    "symbol": trade.symbol,
                    "incomeType": trade.type,
                    "asset": trade.asset,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "side": trade.side,
                    "time": datetime.utcfromtimestamp(trade.timestamp / 1000),
                    "timestamp": trade.timestamp,
                    "account": account}
                    for trade in trades],
            )
            session.commit()

    def process_orders(self, orders: List[Order], account: str):
        with self.lockable_session as session:
            logger.debug('Processing orders')
            session.query(OrderEntity).filter(OrderEntity.account == account).delete()

            for order in orders:
                order_entity = OrderEntity()
                order_entity.symbol = order.symbol
                order_entity.price = order.price
                order_entity.type = order.type
                order_entity.quantity = order.quantity
                order_entity.position_side = order.position_side
                order_entity.side = order.side
                order_entity.status = order.status
                order_entity.account = account
                session.add(order_entity)
            session.commit()

    def get_open_orders(self, symbol: str, account: str) -> List[OrderEntity]:
        with self.lockable_session as session:
            logger.debug(f'Getting orders for {symbol}')
            return session.query(OrderEntity).filter(OrderEntity.symbol == symbol)\
                .filter(OrderEntity.account == account).all()

    def is_symbol_traded(self, symbol: str, account: str) -> bool:
        with self.lockable_session as session:
            logger.debug('Getting traded symbol')
            query = session.query(TradedSymbolEntity).filter(TradedSymbolEntity.symbol == symbol)\
                .filter(TradedSymbolEntity.account == account)
            return session.query(query.exists())

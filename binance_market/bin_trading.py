import concurrent.futures
import threading
from apscheduler.schedulers.background import BackgroundScheduler
import utils
from binance_market import bin_trading_order, bin_trading_run, bin_cancel_order, bin_setting, bin_unsave_order
from binance_market.bin_balance import getBinanceFutureBalance
from config import connect_redis, connect_db


class OrderTradeBIN:
    def __init__(self, param, w_param, rdb):
        self.threading_binance_scheduler = None
        self.param = param
        self.user_num = int(param['user_num'])
        self.coin_num = int(param['coin_num'])
        self.symbol = str(param['coin_name'])
        self.bet_limit = int(param['bet_limit'])
        self.rate_rev = float(param['rate_rev'])
        self.leverage = int(param['leverage'])
        self.rate_liq = float(param['rate_liq'])
        self.api_key = str(param['api_key'])
        self.secret_key = str(param['secret_key'])
        self.dot_digit = int(param['dot_digit'])
        self.min_digit = int(param['min_digit'])

        self.w_param = w_param
        self.reorder_time = int(w_param['m8'])
        self.rdb = rdb

        self.trading_order = None
        self.setting = bin_setting.BinanceSetting()
        self.live_run = None

        self.trade_scheduler = None
        self.onTradingScheduler()
        self.live_instances = []
        self.reset_time = 0
        self.unclose_time = 0

    def del_run(self):
        for instance in self.live_instances:
            self.live_instances.remove(instance)
            instance.shutDownCheckSchedule()
            instance.del_run()
            del instance

    def onTradingScheduler(self):
        self.trade_scheduler = BackgroundScheduler()
        self.trade_scheduler.add_job(self.tradeBinanceScheduler, 'interval', seconds=5, max_instances=50, misfire_grace_time=10, coalesce=True)
        self.trade_scheduler.start()

    def shutDownSchedule(self):
        try:
            if self.trade_scheduler.running:
                self.trade_scheduler.shutdown(wait=False)
            else:
                print("Binance trade_scheduler is not running")
        except Exception as e:
            print(f"Binance trade_scheduler has already been shutdown. {e}")

    def tradeBinanceScheduler(self):
        try:
            if self.trade_scheduler is False:
                return
            with concurrent.futures.ThreadPoolExecutor() as executor:
                works = []
                # 해당 코인의 전체 주문 닫기
                work1 = executor.submit(self.closeBinanceAllOrders)
                works.append(work1)
                # 재주문 시간 후에 주문 새로 넣기
                if self.reset_time >= self.reorder_time:
                    work2 = executor.submit(self.resetBinanceOrder)
                    works.append(work2)
                    self.reset_time = 0
                self.reset_time += 5

                if self.unclose_time >= 60:
                    #work3 = executor.submit(self.saveBinanceClosedOrder)
                    #works.append(work3)
                    self.unclose_time = 0
                self.unclose_time += 5

                concurrent.futures.wait(works)
                executor.shutdown()
        except Exception as e:
            print(f"HTX tradeScheduler error : {e}")

    # 전체 주문 강제 취소
    def closeBinanceAllOrders(self):
        is_cancel = False
        for stop_info in utils.stop_bin_info:
            if stop_info[0] == self.user_num and stop_info[1] == 'bin' and stop_info[2] == self.symbol:
                is_cancel = True
                break
        if is_cancel:
            cancel_order = bin_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
            close_id = cancel_order.onCloseAllPosition(self.symbol, 'bin')
            if close_id != '':
                cancel_order.saveClosePosition(self.symbol, close_id)
            cancel_order.onCancelAllOrder(self.symbol, 'bin')

            i = 0
            for stop_bin in utils.stop_bin_info:
                if stop_bin[2] == self.symbol:
                    del utils.stop_bin_info[i]
                i += 1

            # 청산 후 보관 되지 않은 주문 보관 하기
            unclear_ids = connect_db.getUnSaveTradeIds(self.user_num, 'bin')
            if len(unclear_ids) > 0:
                bin_unsave_order.unSavePositionOrders(self.api_key, self.secret_key, self.user_num, unclear_ids)

            self.setting.initBinanceParams('all')
            self.shutDownSchedule()
            #self.del_run()

    def resetBinanceOrder(self):
        if self.setting.is_brake:
            return
        sell_idx = self.setting.checkBinanceNextIndex(0, 'sell')
        if sell_idx == 0:
            self.run_binance_thread(0, 'sell')
        buy_idx = self.setting.checkBinanceNextIndex(0, 'buy')
        if buy_idx == 0:
            self.run_binance_thread(0, 'buy')

    def saveBinanceClosedOrder(self):
        unclear_ids = connect_db.getUnSaveTradeIds(self.user_num, 'bin')
        if len(unclear_ids) > 0:
            bin_unsave_order.unSavePositionOrders(self.api_key, self.secret_key, self.user_num, unclear_ids)

    def run_binance_thread(self, idx, direction, current_price=0, pre_price=0):
        try:
            self.trading_order = bin_trading_order.BinanceTradeOrder(self.api_key, self.secret_key, self.symbol, self.user_num, self.coin_num, self.dot_digit, self.min_digit)
            balance = getBinanceFutureBalance(self.api_key, self.secret_key)
            if balance is None:
                return
            if float(balance) > 0:
                connect_db.setUsersAmount(self.user_num, 'bin', utils.getRoundDotDigit(float(balance), 2))
            if current_price == 0 or pre_price == 0:
                current_price = connect_redis.getCoinCurrentPrice(self.rdb, 'bin', self.symbol, 'float')
                if current_price == 0:
                    return
                # 이전 가격이 없는 경우 평균 가격 얻기
                pre_price = connect_redis.getCoinMiddlePrice(self.rdb, 'bin', self.symbol)
                if pre_price == 0:
                    pre_price = current_price
            order_thread = threading.Thread(self.onCreateIsolatedTPSL(idx, direction, balance, current_price, pre_price))
            order_thread.start()
        except Exception as e:
            print(f"Binance run_binance_thread() error : {e}")
            return

    # create trading order
    def onCreateIsolatedTPSL(self, idx, direction, balance, current_price, middle_price):
        if current_price == 0 or middle_price == 0:
            return

        volume, lever_rate, strength = self.setParamTrade(idx)
        price = 0
        if direction == "sell":
            base_price = (current_price + middle_price) / 2
            price = current_price + base_price * (self.rate_rev / 100) * strength
        elif direction == "buy":
            base_price = (current_price + middle_price) / 2
            price = current_price - base_price * (self.rate_rev / 100) * strength

        state, order_id, order_price = self.trading_order.binanceOpenLimitOrder(direction, idx, balance, volume, current_price, lever_rate, self.bet_limit, price, self.rate_rev, self.rate_liq)
        if state:
            self.live_run = bin_trading_run.RunTrading(self.api_key, self.secret_key, self.symbol, idx, direction,
                                                       self.param, self.w_param, self.rdb, price, order_id,
                                                       self.setting, self, self.user_num)
            self.live_run.checkOrderExecution(self.trading_order, volume)
            self.live_instances.append(self.live_run)
        else:
            if order_id != '':
                cancel_order = bin_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
                cancel_order.onCancelOrder(order_id, self.symbol)
            self.run_binance_thread(idx, direction)

    # 매매 차수에 따르는 파라미터 변수 설정
    def setParamTrade(self, idx):
        lever_rate = 0
        order_cnt = 0
        strength = 0
        if int(idx) == 0:
            order_cnt = float(self.w_param['m12'])
            lever_rate = self.leverage + int(self.w_param['m20'])
            strength = float(self.w_param['m1'])
        elif int(idx) == 1:
            order_cnt = float(self.w_param['m13'])
            lever_rate = self.leverage + int(self.w_param['m21'])
            strength = float(self.w_param['m2'])
        elif int(idx) == 2:
            order_cnt = float(self.w_param['m14'])
            lever_rate = self.leverage + int(self.w_param['m22'])
            strength = float(self.w_param['m3'])
        elif int(idx) == 3:
            order_cnt = float(self.w_param['m15'])
            lever_rate = self.leverage + int(self.w_param['m23'])
            strength = float(self.w_param['m4'])

        if lever_rate <= 1:
            lever_rate = 1
        lever_rate = self.leverage
        volume = self.bet_limit * order_cnt

        return volume, lever_rate, strength

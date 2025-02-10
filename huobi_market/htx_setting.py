class HuobiSetting:
    def __init__(self):
        self.SELL_PRICE = [0, 0, 0, 0, 0]
        self.SELL_TP = [0, 0, 0, 0, 0]
        self.SELL_SL = [0, 0, 0, 0, 0]
        self.SELL_ID = ['', '', '', '', '']
        self.SELL_RUN = [0, 0, 0, 0, 0]
        self.BUY_PRICE = [0, 0, 0, 0, 0]
        self.BUY_TP = [0, 0, 0, 0, 0]
        self.BUY_SL = [0, 0, 0, 0, 0]
        self.BUY_ID = ['', '', '', '', '']
        self.BUY_RUN = [0, 0, 0, 0, 0]
        self.SELL_STATUS = [0, 0, 0, 0, 0]
        self.BUY_STATUS = [0, 0, 0, 0, 0]
        self.l_stop = False
        self.s_brake = False
        self.is_close = False
        self.max_price = 0
        self.min_price = 0
        self.symbol_price = 0
        self.holding_status = False
        self.SELL_AMOUNT = [0, 0, 0, 0, 0]
        self.BUY_AMOUNT = [0, 0, 0, 0, 0]
        self.SELL_VOLUME = [0, 0, 0, 0, 0]
        self.BUY_VOLUME = [0, 0, 0, 0, 0]
        self.SELL_MONEY = [0, 0, 0, 0, 0]
        self.BUY_MONEY = [0, 0, 0, 0, 0]
        self.SELL_NEXT = [0, 0, 0, 0, 0]
        self.BUY_NEXT = [0, 0, 0, 0, 0]

    def setStOrderStatus(self, idx, status, direction, price=0, tp=0, sl=0, amount=0, volume=0, money=0, order_id=''):
        if status == 'create':
            if direction == 'sell':
                self.SELL_PRICE[idx] = price
                self.SELL_TP[idx] = tp
                self.SELL_SL[idx] = sl
                self.SELL_ID[idx] = order_id
                self.SELL_STATUS[idx] = 6
                self.SELL_RUN[idx] = 1
                self.SELL_AMOUNT[idx] = amount
                self.SELL_VOLUME[idx] = volume
                self.SELL_MONEY[idx] = money
            else:
                self.BUY_PRICE[idx] = price
                self.BUY_TP[idx] = tp
                self.BUY_SL[idx] = sl
                self.BUY_ID[idx] = order_id
                self.BUY_STATUS[idx] = 6
                self.BUY_RUN[idx] = 1
                self.BUY_AMOUNT[idx] = amount
                self.BUY_VOLUME[idx] = volume
                self.BUY_MONEY[idx] = money
        elif status == 'complete':
            if direction == 'sell':
                self.SELL_PRICE[idx] = 0
                self.SELL_TP[idx] = 0
                self.SELL_SL[idx] = 0
                self.SELL_ID[idx] = ''
                self.SELL_STATUS[idx] = 0
                self.SELL_RUN[idx] = 0
                self.SELL_AMOUNT[idx] = 0
                self.SELL_VOLUME[idx] = 0
                self.SELL_MONEY[idx] = 0
                self.SELL_NEXT[idx] = 0
            else:
                self.BUY_PRICE[idx] = 0
                self.BUY_TP[idx] = 0
                self.BUY_SL[idx] = 0
                self.BUY_ID[idx] = ''
                self.BUY_STATUS[idx] = 0
                self.BUY_RUN[idx] = 0
                self.BUY_AMOUNT[idx] = 0
                self.BUY_VOLUME[idx] = 0
                self.BUY_MONEY[idx] = 0
                self.BUY_NEXT[idx] = 0

    def initParams(self):
        self.SELL_PRICE = [0, 0, 0, 0, 0]
        self.SELL_TP = [0, 0, 0, 0, 0]
        self.SELL_SL = [0, 0, 0, 0, 0]
        self.SELL_ID = ['', '', '', '', '']
        self.SELL_RUN = [0, 0, 0, 0, 0]
        self.SELL_STATUS = [0, 0, 0, 0, 0]
        self.BUY_PRICE = [0, 0, 0, 0, 0]
        self.BUY_TP = [0, 0, 0, 0, 0]
        self.BUY_SL = [0, 0, 0, 0, 0]
        self.BUY_ID = ['', '', '', '', '']
        self.BUY_RUN = [0, 0, 0, 0, 0]
        self.BUY_STATUS = [0, 0, 0, 0, 0]
        self.SELL_AMOUNT = [0, 0, 0, 0, 0]
        self.BUY_AMOUNT = [0, 0, 0, 0, 0]
        self.SELL_VOLUME = [0, 0, 0, 0, 0]
        self.BUY_VOLUME = [0, 0, 0, 0, 0]
        self.SELL_MONEY = [0, 0, 0, 0, 0]
        self.BUY_MONEY = [0, 0, 0, 0, 0]
        self.SELL_NEXT = [0, 0, 0, 0, 0]
        self.BUY_NEXT = [0, 0, 0, 0, 0]
        self.l_stop = False
        self.s_brake = False
        self.holding_status = False
        self.is_close = False
        self.max_price = 0
        self.min_price = 0

    # 다음 주문 상태 얻기
    def getNextStatus(self, idx, direction):
        if direction == 'sell':
            return self.SELL_NEXT[idx]
        elif direction == 'buy':
            return self.BUY_NEXT[idx]

    # 다음 주문 상태 설정
    def setNextStatus(self, idx, direction, val):
        if direction == 'sell':
            self.SELL_NEXT[idx] = val
        elif direction == 'buy':
            self.BUY_NEXT[idx] = val

    # 오픈 된 주문의 주문 가격(포지션 될수 있는 가격) 얻기
    def getOrderPrice(self, idx, direction):
        if direction == 'sell':
            return self.SELL_PRICE[idx]
        elif direction == 'buy':
            return self.BUY_PRICE[idx]

    # 오픈 된 주문의 tp, sl 가격 얻기
    def getTpSl(self, idx, direction):
        if direction == 'sell':
            return self.SELL_TP[idx], self.SELL_SL[idx]
        else:
            return self.BUY_TP[idx], self.BUY_SL[idx]

    def getStartOrderIndex(self, direction):
        if direction == 'sell':
            for i in range(4, -1, -1):
                st = self.SELL_STATUS[i]
                if st == 3:
                    return i
        else:
            for i in range(4, -1, -1):
                st = self.BUY_STATUS[i]
                if st == 3:
                    return i
        return 0

    # 주문의 상태 얻기 - 오픈, 포지션, 취소
    def getOrderStatus(self, idx, direction):
        if direction == 'sell':
            return self.SELL_STATUS[idx]
        else:
            return self.BUY_STATUS[idx]

    # 주문의 상태 설정 - 오픈, 포지션, 취소
    def setOrderStatus(self, idx, direction, val):
        if direction == 'sell':
            self.SELL_STATUS[idx] = val
        else:
            self.BUY_STATUS[idx] = val

    # 주문의 실행 상태 얻기
    def getRunStatus(self, idx, direction):
        if direction == 'sell':
            return self.SELL_RUN[idx]
        else:
            return self.BUY_RUN[idx]

    def setRunStatus(self, idx, direction, val):
        if direction == 'sell':
            self.SELL_RUN[idx] = val
        else:
            self.BUY_RUN[idx] = val

    # 심볼의 다음 주문 가능성 확인
    def checkNextIndex(self, idx, direction):
        if direction == 'sell':
            if idx == 0:
                if self.SELL_RUN[0] == 0 and self.SELL_RUN[1] == 0 and self.SELL_RUN[2] == 0 and self.SELL_RUN[3] == 0:
                    return 0
            elif idx == 1:
                if self.SELL_RUN[0] == 1 and self.SELL_RUN[1] == 0 and self.SELL_RUN[2] == 0 and self.SELL_RUN[3] == 0:
                    return 1
                elif self.SELL_RUN[0] == 0 and self.SELL_RUN[1] == 0 and self.SELL_RUN[2] == 0 and self.SELL_RUN[3] == 0:
                    return 0
            elif idx == 2:
                if self.SELL_RUN[0] == 1 and self.SELL_RUN[1] == 1 and self.SELL_RUN[2] == 0 and self.SELL_RUN[3] == 0:
                    return 2
                elif self.SELL_RUN[0] == 1 and self.SELL_RUN[1] == 0 and self.SELL_RUN[2] == 0 and self.SELL_RUN[3] == 0:
                    return 1
                elif self.SELL_RUN[0] == 0 and self.SELL_RUN[1] == 0 and self.SELL_RUN[2] == 0 and self.SELL_RUN[3] == 0:
                    return 0
            elif idx == 3:
                if self.SELL_RUN[3] == 0:
                    if self.SELL_RUN[0] == 0 and self.SELL_RUN[1] == 0 and self.SELL_RUN[2] == 0:
                        return 0
                    elif self.SELL_RUN[0] == 1 and self.SELL_RUN[1] == 0 and self.SELL_RUN[2] == 0:
                        return 1
                    elif self.SELL_RUN[0] == 1 and self.SELL_RUN[1] == 1 and self.SELL_RUN[2] == 0:
                        return 2
                    elif self.SELL_RUN[0] == 1 and self.SELL_RUN[1] == 1 and self.SELL_RUN[2] == 1:
                        return 3
        elif direction == 'buy':
            if idx == 0:
                if self.BUY_RUN[0] == 0 and self.BUY_RUN[1] == 0 and self.BUY_RUN[2] == 0 and self.BUY_RUN[3] == 0:
                    return 0
            elif idx == 1:
                if self.BUY_RUN[0] == 1 and self.BUY_RUN[1] == 0 and self.BUY_RUN[2] == 0 and self.BUY_RUN[3] == 0:
                    return 1
                elif self.BUY_RUN[0] == 0 and self.BUY_RUN[1] == 0 and self.BUY_RUN[2] == 0 and self.BUY_RUN[3] == 0:
                    return 0
            elif idx == 2:
                if self.BUY_RUN[0] == 1 and self.BUY_RUN[1] == 1 and self.BUY_RUN[2] == 0 and self.BUY_RUN[3] == 0:
                    return 2
                elif self.BUY_RUN[0] == 1 and self.BUY_RUN[1] == 0 and self.BUY_RUN[2] == 0 and self.BUY_RUN[3] == 0:
                    return 1
                elif self.BUY_RUN[0] == 0 and self.BUY_RUN[1] == 0 and self.BUY_RUN[2] == 0 and self.BUY_RUN[3] == 0:
                    return 0
            elif idx == 3:
                if self.BUY_RUN[3] == 0:
                    if self.BUY_RUN[0] == 0 and self.BUY_RUN[1] == 0 and self.BUY_RUN[2] == 0:
                        return 0
                    elif self.BUY_RUN[0] == 1 and self.BUY_RUN[1] == 0 and self.BUY_RUN[2] == 0:
                        return 1
                    elif self.BUY_RUN[0] == 1 and self.BUY_RUN[1] == 1 and self.BUY_RUN[2] == 0:
                        return 2
                    elif self.BUY_RUN[0] == 1 and self.BUY_RUN[1] == 1 and self.BUY_RUN[2] == 1:
                        return 3
        return -1

    # 포지션 된 주문의 아이디 얻기
    def getOrderID(self, idx, direction):
        if direction == 'sell':
            return self.SELL_ID[idx]
        else:
            return self.BUY_ID[idx]

    # 심볼의 sell, buy 주문이 모두 포지션 된 경우 인가를 확인
    def getSymbolPositionStatus(self):
        sell_pos = False
        buy_pos = False
        for i in range(0, 4):
            if self.SELL_STATUS[i] == 4 or self.SELL_STATUS[i] == 6:
                sell_pos = True
                break
        for i in range(0, 4):
            if self.BUY_STATUS[i] == 4 or self.BUY_STATUS[i] == 6:
                buy_pos = True
                break
        if sell_pos and buy_pos:
            return True
        else:
            return False

    # 심볼의 sell, buy 주문이 모두 포지션 된 경우 인가를 확인
    def getDirectionStatus(self, direction):
        if direction == 'sell':
            for i in range(0, 4):
                if self.SELL_STATUS[i] > 0:
                    return True
        elif direction == 'buy':
            for i in range(0, 4):
                if self.BUY_STATUS[i] > 0:
                    return True
        return False

    def getVolume(self, idx, direction):
        if direction == 'sell':
            return self.SELL_VOLUME[idx]
        elif direction == 'buy':
            return self.BUY_VOLUME[idx]

    def getOrderMoney(self, idx, direction):
        if direction == 'sell':
            return self.SELL_MONEY[idx]
        elif direction == 'buy':
            return self.BUY_MONEY[idx]

    def getIDX(self, direction, order_id):
        for i in range(0, 5):
            if direction == 'sell':
                if self.SELL_ID[i] == order_id:
                    return i
            elif direction == 'buy':
                if self.BUY_ID[i] == order_id:
                    return i

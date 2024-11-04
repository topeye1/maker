

class BinanceSetting:
    def __init__(self):
        self.BIN_SELL_PRICE = [0, 0, 0, 0]
        self.BIN_SELL_VOLUME = [0, 0, 0, 0]
        self.BIN_SELL_ID = ['', '', '', '']
        self.BIN_SELL_RUN = [0, 0, 0, 0]
        self.BIN_SELL_STATUS = [0, 0, 0, 0]
        self.BIN_SELL_TRIGGER = [0, 0, 0, 0]
        self.BIN_SELL_TPID = ['', '', '', '']
        self.BIN_SELL_SLID = ['', '', '', '']

        self.BIN_BUY_PRICE = [0, 0, 0, 0]
        self.BIN_BUY_VOLUME = [0, 0, 0, 0]
        self.BIN_BUY_ID = ['', '', '', '']
        self.BIN_BUY_RUN = [0, 0, 0, 0]
        self.BIN_BUY_STATUS = [0, 0, 0, 0]
        self.BIN_BUY_TRIGGER = [0, 0, 0, 0]
        self.BIN_BUY_TPID = ['', '', '', '']
        self.BIN_BUY_SLID = ['', '', '', '']

        self.is_bin_all_close = False
        self.is_brake = False

    def setBinanceOrderStatus(self, idx, status, direction, price=0, volume=0, order_id=''):
        if status == 'create':
            if direction == 'sell':
                self.BIN_SELL_PRICE[idx] = price
                self.BIN_SELL_VOLUME[idx] = volume
                self.BIN_SELL_ID[idx] = order_id
                self.BIN_SELL_STATUS[idx] = 1
                self.BIN_SELL_RUN[idx] = 1
            else:
                self.BIN_BUY_PRICE[idx] = price
                self.BIN_BUY_VOLUME[idx] = volume
                self.BIN_BUY_ID[idx] = order_id
                self.BIN_BUY_STATUS[idx] = 1
                self.BIN_BUY_RUN[idx] = 1
        elif status == 'complete':
            if direction == 'sell':
                self.BIN_SELL_PRICE[idx] = 0
                self.BIN_SELL_VOLUME[idx] = 0
                self.BIN_SELL_ID[idx] = ''
                self.BIN_SELL_STATUS[idx] = 0
                self.BIN_SELL_RUN[idx] = 0
                self.BIN_SELL_TRIGGER[idx] = 0
                self.BIN_SELL_TPID[idx] = ''
                self.BIN_SELL_SLID[idx] = ''
            else:
                self.BIN_BUY_PRICE[idx] = 0
                self.BIN_BUY_VOLUME[idx] = 0
                self.BIN_BUY_ID[idx] = ''
                self.BIN_BUY_STATUS[idx] = 0
                self.BIN_BUY_RUN[idx] = 0
                self.BIN_BUY_TRIGGER[idx] = 0
                self.BIN_BUY_TPID[idx] = ''
                self.BIN_BUY_SLID[idx] = ''

    def initBinanceParams(self, direction):
        if direction == 'all':
            self.BIN_SELL_PRICE = [0, 0, 0, 0]
            self.BIN_SELL_VOLUME = [0, 0, 0, 0]
            self.BIN_SELL_ID = ['', '', '', '']
            self.BIN_SELL_RUN = [0, 0, 0, 0]
            self.BIN_SELL_STATUS = [0, 0, 0, 0]
            self.BIN_SELL_TRIGGER = [0, 0, 0, 0]
            self.BIN_BUY_PRICE = [0, 0, 0, 0]
            self.BIN_BUY_VOLUME = [0, 0, 0, 0]
            self.BIN_BUY_ID = ['', '', '', '']
            self.BIN_BUY_RUN = [0, 0, 0, 0]
            self.BIN_BUY_STATUS = [0, 0, 0, 0]
            self.BIN_BUY_TRIGGER = [0, 0, 0, 0]
            self.BIN_SELL_TPID = ['', '', '', '']
            self.BIN_SELL_SLID = ['', '', '', '']
            self.BIN_BUY_TPID = ['', '', '', '']
            self.BIN_BUY_SLID = ['', '', '', '']
        elif direction == 'sell':
            self.BIN_SELL_PRICE = [0, 0, 0, 0]
            self.BIN_SELL_VOLUME = [0, 0, 0, 0]
            self.BIN_SELL_ID = ['', '', '', '']
            self.BIN_SELL_RUN = [0, 0, 0, 0]
            self.BIN_SELL_STATUS = [0, 0, 0, 0]
            self.BIN_SELL_TRIGGER = [0, 0, 0, 0]
            self.BIN_SELL_TPID = ['', '', '', '']
            self.BIN_SELL_SLID = ['', '', '', '']
        else:
            self.BIN_BUY_PRICE = [0, 0, 0, 0]
            self.BIN_BUY_VOLUME = [0, 0, 0, 0]
            self.BIN_BUY_ID = ['', '', '', '']
            self.BIN_BUY_RUN = [0, 0, 0, 0]
            self.BIN_BUY_STATUS = [0, 0, 0, 0]
            self.BIN_BUY_TRIGGER = [0, 0, 0, 0]
            self.BIN_BUY_TPID = ['', '', '', '']
            self.BIN_BUY_SLID = ['', '', '', '']

    def getOrderTrigger(self, idx, direction):
        if direction == 'sell':
            return self.BIN_SELL_TRIGGER[idx]
        else:
            return self.BIN_BUY_TRIGGER[idx]

    def setOrderTrigger(self, idx, direction, val):
        if direction == 'sell':
            self.BIN_SELL_TRIGGER[idx] = val
        else:
            self.BIN_BUY_TRIGGER[idx] = val

    def setTpSlID(self, idx, direction, tpID, slID):
        if direction == 'sell':
            self.BIN_SELL_TPID[idx] = tpID
            self.BIN_SELL_SLID[idx] = slID
        else:
            self.BIN_BUY_TPID[idx] = tpID
            self.BIN_BUY_SLID[idx] = slID

    def getTpSlID(self, idx, direction):
        if direction == 'sell':
            return self.BIN_SELL_TPID[idx], self.BIN_SELL_SLID[idx]
        else:
            return self.BIN_BUY_TPID[idx], self.BIN_BUY_SLID[idx]

    def getIDs(self, idx, direction):
        ids = []
        for i in range(0, idx):
            if direction == 'sell':
                if self.BIN_SELL_ID[i] != '':
                    ids.append(self.BIN_SELL_ID[i])
            else:
                if self.BIN_BUY_ID[i] != '':
                    ids.append(self.BIN_BUY_ID[i])
        return ids

    def getBinanceOrderStatus(self, idx, direction):
        if direction == 'sell':
            return self.BIN_SELL_STATUS[idx]
        else:
            return self.BIN_BUY_STATUS[idx]

    def changeBinanceOrderStatus(self, idx, direction):
        if direction == 'sell':
            self.BIN_SELL_STATUS[idx] = 1
        else:
            self.BIN_BUY_STATUS[idx] = 1

    def cancelBinanceOrderStatus(self, idx, direction):
        if direction == 'sell':
            self.BIN_SELL_STATUS[idx] = 0
        else:
            self.BIN_BUY_STATUS[idx] = 0

    def getBinanceRunStatus(self, idx, direction):
        if direction == 'sell':
            return self.BIN_SELL_RUN[idx]
        else:
            return self.BIN_BUY_RUN[idx]

    def checkBinanceNextIndex(self, idx, direction):
        if direction == 'sell':
            if idx == 0:
                if self.BIN_SELL_RUN[0] == 0 and self.BIN_SELL_RUN[1] == 0 and self.BIN_SELL_RUN[2] == 0 and self.BIN_SELL_RUN[3] == 0:
                    return 0
            elif idx == 1:
                if self.BIN_SELL_RUN[0] == 1 and self.BIN_SELL_RUN[1] == 0 and self.BIN_SELL_RUN[2] == 0 and self.BIN_SELL_RUN[3] == 0:
                    return 1
                elif self.BIN_SELL_RUN[0] == 0 and self.BIN_SELL_RUN[1] == 0 and self.BIN_SELL_RUN[2] == 0 and self.BIN_SELL_RUN[3] == 0:
                    return 0
            elif idx == 2:
                if self.BIN_SELL_RUN[0] == 1 and self.BIN_SELL_RUN[1] == 1 and self.BIN_SELL_RUN[2] == 0 and self.BIN_SELL_RUN[3] == 0:
                    return 2
                elif self.BIN_SELL_RUN[0] == 1 and self.BIN_SELL_RUN[1] == 0 and self.BIN_SELL_RUN[2] == 0 and self.BIN_SELL_RUN[3] == 0:
                    return 1
                elif self.BIN_SELL_RUN[0] == 0 and self.BIN_SELL_RUN[1] == 0 and self.BIN_SELL_RUN[2] == 0 and self.BIN_SELL_RUN[3] == 0:
                    return 0
            elif idx == 3:
                if self.BIN_SELL_RUN[3] == 0:
                    if self.BIN_SELL_RUN[0] == 0 and self.BIN_SELL_RUN[1] == 0 and self.BIN_SELL_RUN[2] == 0:
                        return 0
                    elif self.BIN_SELL_RUN[0] == 1 and self.BIN_SELL_RUN[1] == 0 and self.BIN_SELL_RUN[2] == 0:
                        return 1
                    elif self.BIN_SELL_RUN[0] == 1 and self.BIN_SELL_RUN[1] == 1 and self.BIN_SELL_RUN[2] == 0:
                        return 2
                    elif self.BIN_SELL_RUN[0] == 1 and self.BIN_SELL_RUN[1] == 1 and self.BIN_SELL_RUN[2] == 1:
                        return 3
        elif direction == 'buy':
            if idx == 0:
                if self.BIN_BUY_RUN[0] == 0 and self.BIN_BUY_RUN[1] == 0 and self.BIN_BUY_RUN[2] == 0 and self.BIN_BUY_RUN[3] == 0:
                    return 0
            elif idx == 1:
                if self.BIN_BUY_RUN[0] == 1 and self.BIN_BUY_RUN[1] == 0 and self.BIN_BUY_RUN[2] == 0 and self.BIN_BUY_RUN[3] == 0:
                    return 1
                elif self.BIN_BUY_RUN[0] == 0 and self.BIN_BUY_RUN[1] == 0 and self.BIN_BUY_RUN[2] == 0 and self.BIN_BUY_RUN[3] == 0:
                    return 0
            elif idx == 2:
                if self.BIN_BUY_RUN[0] == 1 and self.BIN_BUY_RUN[1] == 1 and self.BIN_BUY_RUN[2] == 0 and self.BIN_BUY_RUN[3] == 0:
                    return 2
                elif self.BIN_BUY_RUN[0] == 1 and self.BIN_BUY_RUN[1] == 0 and self.BIN_BUY_RUN[2] == 0 and self.BIN_BUY_RUN[3] == 0:
                    return 1
                elif self.BIN_BUY_RUN[0] == 0 and self.BIN_BUY_RUN[1] == 0 and self.BIN_BUY_RUN[2] == 0 and self.BIN_BUY_RUN[3] == 0:
                    return 0
            elif idx == 3:
                if self.BIN_BUY_RUN[3] == 0:
                    if self.BIN_BUY_RUN[0] == 0 and self.BIN_BUY_RUN[1] == 0 and self.BIN_BUY_RUN[2] == 0:
                        return 0
                    elif self.BIN_BUY_RUN[0] == 1 and self.BIN_BUY_RUN[1] == 0 and self.BIN_BUY_RUN[2] == 0:
                        return 1
                    elif self.BIN_BUY_RUN[0] == 1 and self.BIN_BUY_RUN[1] == 1 and self.BIN_BUY_RUN[2] == 0:
                        return 2
                    elif self.BIN_BUY_RUN[0] == 1 and self.BIN_BUY_RUN[1] == 1 and self.BIN_BUY_RUN[2] == 1:
                        return 3
        return -1

    def getBinanceOrderID(self, idx, direction):
        if direction == 'sell':
            return self.BIN_SELL_ID[idx]
        else:
            return self.BIN_BUY_ID[idx]

    def getBinanceOrderPrice(self, idx, direction):
        if direction == 'sell':
            price = self.BIN_SELL_PRICE[idx]
            return price
        else:
            price = self.BIN_BUY_PRICE[idx]
            return price

    def getAverageOrderPrice(self, idx, direction):
        count = idx + 1
        total_val = 0
        total_limit = 0
        if direction == 'sell':
            for i in range(0, count):
                total_limit += self.BIN_SELL_VOLUME[i]
                total_val += self.BIN_SELL_PRICE[i] * self.BIN_SELL_VOLUME[i]
            avr_price = total_val / total_limit
            return avr_price
        else:
            for i in range(0, count):
                total_limit += self.BIN_BUY_VOLUME[i]
                total_val += self.BIN_BUY_PRICE[i] * self.BIN_BUY_VOLUME[i]
            avr_price = total_val / total_limit
            return avr_price

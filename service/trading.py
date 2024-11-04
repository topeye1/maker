from service import MakerLiveService


def onMakerLive(datas, w_param):
    for data in datas:
        trading_bot = MakerLiveService(data, w_param)
        market = str(data['market'])
        if market == "htx":
            trading_bot.startOrderTradingHTX()
            continue
        elif market == "bin":
            #trading_bot.startOrderTradingBIN()
            continue


def onRemoveScheduler(scheduler):
    scheduler.shutdown()
    del scheduler

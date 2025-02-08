from service import MakerLiveService


def onMakerLive(datas, w_param):
    for data in datas:
        make_live = MakerLiveService(data, w_param)
        market = str(data['market'])
        if market == "htx":
            make_live.startOrderTradingHTX()
            continue
        elif market == "bin":
            #make_live.startOrderTradingBIN()
            continue


def onRemoveScheduler(scheduler):
    scheduler.shutdown()
    del scheduler

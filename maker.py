import copy
import time

import utils
from config import ConnDB, connect_db
from service import onMakerLive


def compareArray(arr1, arr2):
    d_arr = []
    for arr in arr1:
        if arr not in arr2:
            d_arr.append(arr)
    return d_arr


def main():
    utils.live_symbols_info = []
    run = True
    while run:
        try:
            w_param = connect_db.getParameters()
            coins = connect_db.getLiveCoins()
            if coins is None or len(coins) == 0:
                if len(utils.live_symbols_info) > 0:
                    for old in utils.live_symbols_info:
                        info = [old['user_num'], old['market'], old['coin_name']]
                        if old['market'] == 'htx':
                            utils.stop_htx_info.append(info)
                        elif old['market'] == 'bin':
                            utils.stop_bin_info.append(info)
                        utils.live_symbols_info.remove(old)
                continue
            if len(utils.live_symbols_info) > 0:
                if len(utils.live_symbols_info) < len(coins):
                    new_coins = compareArray(coins, utils.live_symbols_info)
                    if len(new_coins) > 0:
                        utils.live_symbols_info.extend(new_coins)
                        onMakerLive(new_coins, w_param)
                elif len(utils.live_symbols_info) > len(coins):
                    old_coins = compareArray(utils.live_symbols_info, coins)
                    for old in old_coins:
                        info = [old['user_num'], old['market'], old['coin_name']]
                        if old['market'] == 'htx':
                            utils.stop_htx_info.append(info)
                        elif old['market'] == 'bin':
                            utils.stop_bin_info.append(info)
                        utils.live_symbols_info.remove(old)
            else:
                utils.live_symbols_info = copy.deepcopy(coins)
                onMakerLive(utils.live_symbols_info, w_param)
            time.sleep(3)
        except Exception as e:
            print(e)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

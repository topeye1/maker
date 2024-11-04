import base64
import hashlib
import hmac
from datetime import datetime
from urllib.parse import urlencode

BIN_Uri = 'https://fapi.binance.com'
BIN_Balance = '/fapi/v2/balance'  # 거래소 보유 금액 조회
BIN_Order = '/fapi/v1/order'  # 선물 거래 주문 요청 및 취소

HTX_Uri = 'api.hbdm.com'
HTX_Balance = '/linear-swap-api/v3/unified_account_info'  # 거래소 보유 금액 조회
HTX_Order = '/linear-swap-api/v1/swap_order'  # 새로운 주문 요청
HTX_ChangeLeverage = '/linear-swap-api/v1/swap_cross_switch_lever_rate'  # 레버리지 수정
HTX_OrderInfo = '/linear-swap-api/v1/swap_order_info'  # 선물 거래 주문 체결 상태 확인
HTX_OrderDetail = '/linear-swap-api/v1/swap_order_detail'  # 청산된 선물 거래 상세 보기
HTX_OrderHistory = '/linear-swap-api/v3/swap_hisorders'  # 청산된 선물 거래 목록
HTX_CancelOrder = '/linear-swap-api/v1/swap_cancel'  # 선물 거래 취소
HTX_CancelAllOrder = '/linear-swap-api/v1/swap_cancelall'  # 선물 거래 열린 주문 전체 취소
HTX_CloseTrigger = '/linear-swap-api/v1/swap_trigger_cancelall'  # 선물 거래 체결 된 주문 강제 청산
HTX_PositionInfo = '/linear-swap-api/v1/swap_account_info'  # 선물 거래 포지션 정보
HTX_ClosePosition = '/linear-swap-api/v1/swap_lightning_close_position'  # 선물 거래 체결 된 주문 강제 청산


def setPostApiUrl(api_key, secret_key, method, endpoint):
    hostname = HTX_Uri

    timestamp = str(datetime.utcnow().isoformat())[0:19]
    params = urlencode({
        'AccessKeyId': api_key,
        'SignatureMethod': 'HmacSHA256',
        'SignatureVersion': '2',
        'Timestamp': timestamp
    })
    payload = "\n".join([method, hostname, endpoint, params])
    hash_code = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).digest()
    signature = urlencode({'Signature': base64.b64encode(hash_code).decode()})
    api_url = 'https://' + hostname + endpoint + '?' + params + '&' + signature

    return api_url

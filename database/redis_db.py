import redis
from dotenv import load_dotenv
import os

load_dotenv()


class RedisDB:
    def __init__(self) -> None:
        self.redis_db = redis.Redis(host=os.getenv('REDIS_HOST'), port=os.getenv('REDIS_PORT'), password=os.getenv('REDIS_PASSWORD'), db=0)

    def get(self, variable, val_type="str"):
        try:
            if val_type == 'str':
                return str(self.redis_db.get(variable).decode("utf-8"))
            elif val_type == 'float':
                value = self.redis_db.get(variable)
                if value is not None:
                    return float(self.redis_db.get(variable))
                else:
                    return 0
        except Exception as e:
            print("redis get error: ", e)

    def hget(self, variable, field):
        return self.redis_db.hget(variable, field)

    def hvals(self, variable):
        return self.redis_db.hvals(variable)

    def hmset(self, variable, payload):
        return self.redis_db.hmset(variable, payload)

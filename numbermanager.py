import time
from collections import OrderedDict
from threading import Lock


class NumberManager:
    controlLock = Lock()
    removeTime = 30

    def __init__(self,remove_time=30):
        self.numbers = []
        self.removeTime = remove_time

    def add(self, number):
        """添加数字并记录当前时间戳"""
        current_time = time.time()
        with self.controlLock:
            self.numbers.append({"number": number, "ctime": current_time})

    def remove(self):
        """删除30分钟前添加的数字"""
        current_time = time.time()
        thirty_min_ago = current_time - self.removeTime * 60

        to_delete = []

        for num in self.numbers:
            ctime = num["ctime"]
            if ctime < thirty_min_ago:
                to_delete.append(num)
        with self.controlLock:
            for num in to_delete:
                self.numbers.remove(num)

    def get_count(self):
        """获取当前数字的总数"""
        count = 0
        with self.controlLock:
            for num in self.numbers:
                count += num["number"]
        return count

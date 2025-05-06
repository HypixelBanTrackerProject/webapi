from apscheduler.schedulers.asyncio import AsyncIOScheduler
from numbermanager import NumberManager
from fastapi import FastAPI, Response
import requests
from threading import Lock
import time
from datetime import datetime
from timecalc import time_since
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent
from zoneinfo import ZoneInfo

tz = ZoneInfo("Asia/Shanghai")

session = requests.Session()
retry = Retry(total=30, backoff_factor=1)

adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)
session.mount("http://", adapter)

app = FastAPI()

scheduler = AsyncIOScheduler()

banHistoryExample = {
    "time": 0,
    "formated": "00:00:00",
    "watchdog": False,  # if the ban is from watchdog
    "number": 1,
}

banHistory = []
LockBanHistory = Lock()

watchdog = {
    "last_minute": 0,
    "last_day": 0,
    "total": -1,
}

staffHalfHourCalc = NumberManager()

staff = {
    "last_half_hour": 0,
    "last_day": 0,
    "total": -1,
}

lastUpdated = time.time()


@scheduler.scheduled_job("interval", seconds=6, id="getBanData")
async def getBanData():
    global staff, watchdog, staffHalfHourCalc, banHistory, LockBanHistory, lastUpdated, tz
    punishmentStats = session.get(
        "https://api.plancke.io/hypixel/v1/punishmentStats",
        headers={
            "User-Agent": UserAgent().random,
            "Referer": "https://plancke.io/",
            "Accept": "application/json",
        },
    ).json()["record"]
    staff["last_day"] = punishmentStats["staff_rollingDaily"]
    watchdog["last_day"] = punishmentStats["watchdog_rollingDaily"]
    watchdog["last_minute"] = punishmentStats["watchdog_lastMinute"]

    if staff["total"] == -1 or watchdog["total"] == -1:
        staff["total"] = punishmentStats["staff_total"]
        watchdog["total"] = punishmentStats["watchdog_total"]
        lastUpdated = time.time()
        return

    wdiff = punishmentStats["watchdog_total"] - watchdog["total"]
    sdiff = punishmentStats["staff_total"] - staff["total"]

    if wdiff <= 0 and sdiff <= 0:
        staff["total"] = punishmentStats["staff_total"]
        watchdog["total"] = punishmentStats["watchdog_total"]
        lastUpdated = time.time()
        return

    now = time.time()
    ndatetime = datetime.fromtimestamp(now, tz=tz)

    with LockBanHistory:
        while len(banHistory) > 10:
            banHistory.pop()

        if wdiff > 0:
            data = banHistoryExample.copy()
            data["time"] = now
            data["watchdog"] = True
            data["number"] = wdiff
            data["formated"] = f"{ndatetime:%H:%M:%S}"
            banHistory.insert(0, data)

        if sdiff > 0:
            data = banHistoryExample.copy()
            data["time"] = now
            data["watchdog"] = False
            data["number"] = sdiff
            data["formated"] = f"{ndatetime:%H:%M:%S}"
            staffHalfHourCalc.add(sdiff)
            banHistory.insert(0, data)

    staff["total"] = punishmentStats["staff_total"]
    watchdog["total"] = punishmentStats["watchdog_total"]
    lastUpdated = time.time()


# remove the number that is older than 30 minutes
@scheduler.scheduled_job("interval", seconds=3, id="removeHalfHour")
async def _():
    staffHalfHourCalc.remove()
    staff["last_half_hour"] = staffHalfHourCalc.get_count()


@app.on_event("startup")
async def _():
    await getBanData()
    scheduler.start()


@app.on_event("shutdown")
async def _():
    scheduler.shutdown()


@app.get("/")
async def _():
    global staff, watchdog, banHistory, LockBanHistory, lastUpdated, tz
    with LockBanHistory:
        return {
            "staff": staff,
            "watchdog": watchdog,
            "banHistory": banHistory,
            "lastUpdated": {
                "timestamp": lastUpdated,
                "formated": datetime.fromtimestamp(lastUpdated, tz=tz).strftime(
                    "%H:%M:%S"
                ),
            },
        }


def getAgo(gtime):
    nd = datetime.fromtimestamp(gtime, tz=tz)
    return f"{nd:%H:%M:%S} {time_since(gtime)}"


@app.get("/wdr")
async def _():
    global watchdog, staff, banHistory, LockBanHistory, lastUpdated
    with LockBanHistory:
        list = f"""🐕🐕 Hypixel Ban Tracker 👮‍👮‍
[🐕] 过去一分钟有 {watchdog['last_minute']} 人被狗咬了
[🐕‍] 狗在过去二十四小时内已封禁 {watchdog['last_day']} 人,

[👮‍] 过去的半小时有 {staff['last_half_hour']} 人被逮捕了
[👮‍] 客服在过去二十四小时内已封禁 {staff['last_day']} 人,

上次更新: {getAgo(lastUpdated) }
"""
        if len(banHistory) == 0:
            list += "无最近封禁"
        else:
            list += "最近封禁记录:\n"
            for ban in banHistory:
                list += f"[{'🐕' if ban['watchdog'] else '👮'}] [{ban['formated']}] banned {ban['number']} player.\n"
            list = list[:-1]

    return {"wdr": list}


@app.get("/wdr/raw")
async def _():
    global watchdog, staff, banHistory, LockBanHistory, lastUpdated
    with LockBanHistory:
        list = f"""🐕🐕 Hypixel Ban Tracker 👮‍👮‍
[🐕] 过去一分钟有 {watchdog['last_minute']} 人被狗咬了
[🐕‍] 狗在过去二十四小时内已封禁 {watchdog['last_day']} 人,

[👮‍] 过去的半小时有 {staff['last_half_hour']} 人被逮捕了
[👮‍] 客服在过去二十四小时内已封禁 {staff['last_day']} 人,

上次更新: {getAgo(lastUpdated) }
"""
        if len(banHistory) == 0:
            list += "无最近封禁"
        else:
            list += "最近封禁记录:\n"
            for ban in banHistory:
                list += f"[{'🐕' if ban['watchdog'] else '👮'}] [{ban['formated']}] banned {ban['number']} player.\n"
            list = list[:-1]

    return Response(content=list, media_type="text/plain")

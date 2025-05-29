import json
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
import uvicorn
import os

saveData = None
if os.path.exists("save/save.json"):
    with open("save/save.json", "r", encoding="utf-8") as f:
        saveData = json.loads(f.read())

tz = ZoneInfo("Asia/Shanghai")

session = requests.Session()
retry = Retry(total=30, backoff_factor=1)

adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)
session.mount("http://", adapter)

app = FastAPI()

# Configure FastAPI to run on port 8963

# This configuration will be used when you run the app directly
# For example: if __name__ == "__main__": uvicorn.run("app:app", host="0.0.0.0", port=8963)
# But won't affect when imported as a module

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
    "last_half_hour": 0,
    "last_day": 0,
    "total": -1,
}

staffHalfHourCalc = NumberManager(remove_time=30)
staffLastMinuteCalc = NumberManager(remove_time=1)

watchdogHalfHourCalc = NumberManager(remove_time=30)

staff = {
    "last_minute": 0,
    "last_half_hour": 0,
    "last_day": 0,
    "total": -1,
}

lastUpdated = time.time()

if saveData:
    watchdog["last_day"] = saveData['dog']['last_day']
    watchdog["last_half_hour"] = saveData['dog']['last_half_hour']
    watchdog["last_minute"] = saveData['dog']['last_minute']
    watchdog["total"] = saveData['dog']['total']

    staff["last_day"] = saveData['staff']['last_day']
    staff["last_half_hour"] = saveData['staff']['last_half_hour']
    staff["last_minute"] = saveData['staff']['last_minute']
    staff["total"] = saveData['staff']['total']

    for history in saveData['history']:
        data = banHistoryExample.copy()
        data['time'] = history['time']
        data['formated'] = history['formated']
        data['watchdog'] = history['watchdog']
        data['number'] = history['number']
        banHistory.append(data)

    for data in saveData['number']['staff']['halfhour']:
        staffHalfHourCalc.insert(data['number'],data['ctime'])

    for data in saveData['number']['staff']['lastminute']:
        staffLastMinuteCalc.insert(data['number'],data['ctime'])

    for data in saveData['number']['dog']['halfhour']:
        watchdogHalfHourCalc.insert(data['number'],data['ctime'])

def saveBanData():
    global watchdog,staff,watchdogHalfHourCalc,staffHalfHourCalc,staffLastMinuteCalc,banHistory

    sdata = {}

    sdata['dog'] = {
        "last_day" : watchdog['last_day'],
        "last_minute" : watchdog['last_minute'],
        "last_half_hour" : watchdog["last_half_hour"],
        "total" : watchdog["total"],
    }

    sdata['staff'] = {
        "last_day" : staff['last_day'],
        "last_minute" : staff['last_minute'],
        "last_half_hour" : staff["last_half_hour"],
        "total" : staff["total"],
    }

    sdata['history'] = []
    for h in banHistory:
        sdata['history'].append(h)

    sdata['number'] = {
        'dog':{
            'halfhour': watchdogHalfHourCalc.get_ary()
        },
        'staff':{
            'halfhour': staffHalfHourCalc.get_ary(),
            'lastminute':staffLastMinuteCalc.get_ary()
        }
    }

    with open('save/save.json','w') as f:
        f.write(json.dumps(sdata))

@scheduler.scheduled_job("interval", seconds=6, id="getBanData")
async def getBanData():
    global staff, watchdog, staffHalfHourCalc, banHistory, LockBanHistory, lastUpdated, tz
    try:
        response = session.get(
            "https://api.plancke.io/hypixel/v1/punishmentStats",
            headers={
                "User-Agent": UserAgent().random,
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
            },
            timeout=3,
        )

        response.raise_for_status()

        if response.status_code != 200:
            return

        data = response.json()
        if "record" not in data:
            print(f"Error: 'record' not found in response: {data}")
            return

        punishmentStats = data["record"]

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
                watchdogHalfHourCalc.add(wdiff)
                banHistory.insert(0, data)

            if sdiff > 0:
                data = banHistoryExample.copy()
                data["time"] = now
                data["watchdog"] = False
                data["number"] = sdiff
                data["formated"] = f"{ndatetime:%H:%M:%S}"
                staffHalfHourCalc.add(sdiff)
                staffLastMinuteCalc.add(sdiff)
                banHistory.insert(0, data)

        staff["total"] = punishmentStats["staff_total"]
        watchdog["total"] = punishmentStats["watchdog_total"]
        lastUpdated = time.time()
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return
    except ValueError as e:
        print(f"JSON decode error: {e}")
        print(f"Response content: {response.text}")
        return
    except KeyError as e:
        print(f"Key error: {e}")
        print(f"Available keys: {data.keys() if 'data' in locals() else 'N/A'}")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        return


# remove the number that is older than 30 minutes
@scheduler.scheduled_job("interval", seconds=3, id="numbercalc")
async def _():
    staffHalfHourCalc.remove()
    staff["last_half_hour"] = staffHalfHourCalc.get_count()

    watchdogHalfHourCalc.remove()
    watchdog["last_half_hour"] = watchdogHalfHourCalc.get_count()

    staffLastMinuteCalc.remove()
    staff["last_minute"] = staffLastMinuteCalc.get_count()


@app.on_event("startup")
async def _():
    await getBanData()
    scheduler.start()


@app.on_event("shutdown")
async def _():
    
    saveBanData()

    scheduler.shutdown()


@app.get("/")
async def _():
    global staff, watchdog, banHistory, LockBanHistory, lastUpdated, tz
    with LockBanHistory:
        response = {
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

        return Response(
            content=json.dumps(response, ensure_ascii=False),
            media_type="application/json; charset=utf-8",
            headers={
                "Cache-Control": "max-age=3, must-revalidate",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
            }
        )


def getAgo(gtime):
    nd = datetime.fromtimestamp(gtime, tz=tz)
    return f"{nd:%H:%M:%S} {time_since(gtime)}"


def getWdrMessage() -> str:
    global watchdog, staff, banHistory, LockBanHistory, lastUpdated
    with LockBanHistory:
        list = f"""🐕🐕 Hypixel Ban Tracker 👮‍👮‍
[🐕] 过去一分钟有 {watchdog['last_minute']} 人被狗咬了
[🐕] 过去半小时有 {watchdog['last_half_hour']} 人被狗咬了
[🐕‍] 狗在过去二十四小时内已封禁 {watchdog['last_day']} 人,

[👮‍] 过去的一分钟有 {staff['last_minute']} 人被逮捕了
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
    return list


@app.get("/wdr")
async def _():
    list = getWdrMessage()

    return Response(
        content=json.dumps({"wdr": list}, ensure_ascii=False),
        media_type="application/json; charset=utf-8",
        headers={"Cache-Control": "max-age=3, must-revalidate"},
    )


@app.get("/wdr/raw")
async def _():
    list = getWdrMessage()

    # 添加cache-control头部
    return Response(
        content=list,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "max-age=3, must-revalidate"},
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8963)

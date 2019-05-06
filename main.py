

import re
import os
import shutil
import requests
import requests.exceptions
import json

from pprint import pprint
from datetime import date, timedelta
import time
import traceback
import random
import asyncio
import aiohttp
import aiohttp.client_exceptions



class Skip(Exception):
    pass

class Retry(Exception):
    pass

WECHAT_UA = "Mozilla/5.0 (Linux; Android 9; TWOPLUS A6010 Build/PKQ1.180716.001; wv) " + \
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/66.0.3359.126 " + \
    "MQQBrowser/6.2 TBS/044607 Mobile Safari/537.36 MMWEBID/4820 MicroMessenger/7.0.4.1420(0x27000439) " + \
    "Process/tools NetType/WIFI Language/ja"

__headers__ = {
    "User-Agent": WECHAT_UA,
}

__dir__ = os.path.dirname(__file__)


START_URL = "http://data.people.com.cn/rmrb/19460515/1"

date_pattern = re.compile(
    r'<div class="date">.*?<span>(\d+)</span>年.*?<span>(\d+)</span>月.*?<span>(\d+)</span>日.*?' + \
    r'今日<span id="UseRmrbPageNum">(\d+)</span>版.*?文章<span id="UseRmrbNum">(\d+)</span>篇',
    re.DOTALL | re.MULTILINE | re.UNICODE
)

info_pattern = re.compile(
    r'<div class="info">.*?第<span>(\d+)</span>版\s+?(\[<span>(.*?)</span>\])?\s*?文章<span>(\d+)</span>篇',
    re.DOTALL | re.MULTILINE | re.UNICODE
)

article_link_pattern = re.compile(
    r'<a title="(.*?)" href="(.*?)">',
    re.UNICODE
)

sketchpic_pattern = re.compile(
    r'<img src="([^"]*?)" id="pagesketch"',
)


proxy_addrs = ['http://136.228.128.6:59457',
 'http://218.24.16.198:32621',
 'http://221.210.120.153:54402',
 'http://118.181.226.216:58654',
 'http://119.179.151.220:8060',
 'http://110.189.152.86:33712',
 'http://59.37.33.62:50686',
 'http://136.228.129.36:41838',
 'http://117.131.99.210:53281',
 'http://47.104.201.136:53281',
 'http://61.163.247.10:8118',
 'http://112.16.172.107:59650',
 'http://58.22.177.14:9999',
 'http://47.104.201.136:53281',
 'http://136.228.128.6:59457',
 'http://136.228.128.14:61158',
 'http://121.232.194.75:9000',
 'http://182.92.233.137:8118',
 'http://123.132.232.254:61017',
 'http://219.159.38.207:56210',
 'http://121.13.252.62:41564',
 'http://136.228.128.14:61158',
 'http://115.238.42.211:44919',
 'http://112.14.47.6:52024',
 'http://218.75.70.3:8118',
 'http://222.170.101.98:50204',
 'http://117.131.99.210:53281',
 'http://106.15.42.179:33543',
 'http://111.75.223.9:30646',
 'http://222.135.92.68:38094',
 'http://60.217.64.237:63141',
 'http://117.131.99.210:53281',
 'http://47.98.183.137:8082',
 'http://113.12.202.50:50327',
 'http://117.93.81.127:53281',
 'http://117.131.99.210:53281',
 'http://163.204.245.13:9999',
 'http://60.13.42.72:9999',
 'http://117.91.232.80:9999',
 'http://123.206.201.35:8118',
 'http://163.204.245.252:9999',
 'http://211.152.33.24:51277',
 'http://59.37.33.62:50686',
 'http://47.104.201.136:53281',
 'http://211.152.33.24:51277',
 'http://202.104.150.130:58729',
 'http://111.43.70.58:51547',
 'http://112.14.47.6:52024',
 'http://121.40.138.161:8000',
 'http://139.196.51.201:8118',
 'http://117.114.149.66:53281',
 'http://120.78.145.111:80',
 'http://163.204.242.147:9999',
 'http://221.6.32.214:41816',
 'http://49.86.180.162:9999']



class RiRenMinBao(object):
    def __init__(self, name, queue, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = name
        self.proxy_list = proxy_addrs[:]
        self.proxy = ''
        self.queue = queue

    async def request(self, url):
        timeout = aiohttp.ClientTimeout(total=10)
        while True:
            try:
                async with aiohttp.ClientSession(headers=__headers__) as sess:
                    async with sess.get(url, proxy=self.proxy, timeout=timeout) as resp:
                        headers = resp.headers
                        if int(headers['X-PropertyRateLimiting-Remaining-Hour']) < 10 or \
                                int(headers['X-PropertyRateLimiting-Remaining-Minute']) < 10 or \
                                int(headers['X-PropertyRateLimiting-Remaining-Day']) < 10:
                            raise Retry
                        html = await resp.text()
                        return resp, resp.headers, html
            except Exception as e:
                # print(f'request got error: {e} {type(e)}')
                self.switch_proxy()

    def get_article(self, year, month, day, face, hash):
        title_pattern = re.compile(r'<div class="title">(.*?)</div>')
        subtitle_pattern = re.compile(r'<div class="subtitle">(.*?)</div>')
        author_pattern = re.compile(r'<div class="author">(.*?)</div>')
        title_pattern = re.compile(r'<div class="title">(.*?)</div>')
        article_info_pattern = re.compile(
            r'<div class="sha_left">.*?【人民日报<span>([\d\-]+)</span>\s+第<span>(\d+)</span>版\s+(<span>(.*?)</span>)?.*?</div>',
            re.MULTILINE
        )
        content_pattern = re.compile(
            r'<div id="FontZoom"\s+class="detail_con">\s+(.*?)\s+</div>',
            re.MULTILINE | re.DOTALL
        )
        test_url = 'http://data.people.com.cn/rmrb/20190430/11/d597efcbc59a4c3b8f005529649e230b'


        return

    async def get_face_meta(self, year, month, day, face=1):
        url = "http://data.people.com.cn/rmrb/%d%02d%02d/%d" % (year, month, day, face)

        resp, headers, html = await self.request(url)
        if str(resp.url) != url:
            print(f'{self.name} url redirected {repr(url)} > {resp.url}')
            raise Skip

        try:
            article_part = html.split('class="title_list">')[1].split('class="index_banshi">')[0]
            y, m, d, total_faces, total_articles = date_pattern.findall(html)[0]
            face, has_face_type, face_type, narticle = info_pattern.findall(html)[0]
            articles = article_link_pattern.findall(article_part)
            sketchpic = sketchpic_pattern.findall(html)[0]
        except (IndexError, aiohttp.client_exceptions.ClientConnectionError):
            raise Retry

        meta = dict(
            year=y,
            month=m,
            day=d,
            nface=total_faces,
            narticle=total_articles,
        )

        if int(day) != int(d) or int(year) != int(y):
            print(html)
            print(f'{self.name} date error')
            raise Skip

        face_meta = dict(
            narticle=narticle,
            articles=articles,
            sketchpic=sketchpic,
            type=face_type or '',
        )

        return meta, face_meta

    def switch_proxy(self):
        if not self.proxy_list:
            print("proxy list empty")
            raise SystemExit
        self.proxy = random.choice(self.proxy_list)
        print(f'{self.name} change proxy={self.proxy}')


    async def visit(self, year, month, day):
        path = os.path.join(__dir__, "data/%04d/%02d/%02d" % (year, month, day))
        if os.path.exists(path):
            with open(os.path.join(path, "meta.json")) as fp:
                meta = json.load(fp)
#            print(year, month, day, 'skip 1 face')
            nface = int(meta['nface'])

            if os.path.exists(f'{path}/{nface}/meta.json'):
                print(f'{self.name} {year}/{month}/{day} */{nface} ok')
                return # this is ok
            else:
                for face in range(2, nface+1):
                    while True:
                        try:
                            _, fmeta = await self.get_face_meta(year, month, day, face)
                            print(f'{self.name} {year}/{month}/{day} {face}/{nface}>> {fmeta}')
                            os.makedirs(f'{path}/{face}')
                            with open(f'{path}/{face}/meta.json', 'w') as fp:
                                json.dump(fmeta, fp, ensure_ascii=False)
                            break
                        except Skip:
                            print(f'{self.name} skip {year}/{month}/{day} {face}/{nface}')
                            break
                        except Retry:
                            self.switch_proxy()
                            continue

        else:
            while True:
                try:
                    meta, fmeta = await self.get_face_meta(year, month, day, 1)
                    print(">> ", meta, fmeta)
                    if not meta:
                        return # yep
                    os.makedirs(os.path.join(path, "1"))
                    with open(f'{path}/meta.json', 'w') as fp:
                        json.dump(meta, fp, ensure_ascii=False)

                    with open(os.path.join(path, "1", "meta.json"), 'w') as fp:
                        json.dump(fmeta, fp, ensure_ascii=False)
                    return await self.visit(year, month, day)
                except Skip:
                    print(f'{self.name} skip {year}/{month}/{day}')
                    return
                except Retry:
                    self.switch_proxy()
                    continue


    async def loop(self):
        task = True
        while task:
            task = await self.queue.get()
            if not task:
                print(f'{self.name} DONE!!')
                return

            year, month, day = task
            print(f'{self.name} got {task}!!')
            await self.visit(year, month, day)
            self.queue.task_done()


async def worker(name, queue):
    rmrb = RiRenMinBao(name, queue)
    await rmrb.loop()

async def main():
    queue = asyncio.Queue()
    N = 30
    tasks = []
    for i in range(N):
        task = asyncio.create_task(worker(f'worker-{i+1}', queue))
        tasks.append(task)

    #initial_day = date(1946, 5, 15)
    initial_day = date(2019, 4, 15)
    day = initial_day

    while day <= date.today():
        path = os.path.join(__dir__, f'data/{day.year}/{day.month:02d}/{day.day:02d}')
        #if os.path.exists(path):
        queue.put_nowait((day.year, day.month, day.day))
        day += timedelta(1)

    # queue.put_nowait((1946, 6, 28))

    for i in range(N):
        queue.put_nowait(None)

    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())

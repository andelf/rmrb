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


WECHAT_UA = "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36"

__headers__ = {"User-Agent": WECHAT_UA, 'Accept': 'text/html'}

__dir__ = os.path.dirname(__file__)


START_URL = "http://data.people.com.cn/rmrb/19460515/1"

date_pattern = re.compile(
    r'<div class="date">.*?<span>(\d+)</span>年.*?<span>(\d+)</span>月.*?<span>(\d+)</span>日.*?'
    + r'今日<span id="UseRmrbPageNum">(\d+)</span>版.*?文章<span id="UseRmrbNum">(\d+)</span>篇',
    re.DOTALL | re.MULTILINE | re.UNICODE,
)

info_pattern = re.compile(
    r'<div class="info">.*?第<span>(\d+)</span>版\s+?(\[<span>(.*?)</span>\])?\s*?文章<span>(\d+)</span>篇',
    re.DOTALL | re.MULTILINE | re.UNICODE,
)

article_link_pattern = re.compile(r'<a title="(.*?)" href="(.*?)">', re.UNICODE)

sketchpic_pattern = re.compile(r'<img src="([^"]*?)" id="pagesketch"')


proxy_addrs = [
    'http://221.1.200.242:43399',
    'http://120.234.138.99:53779',
    'http://111.72.25.250:9999',
    'http://60.2.44.182:47293',
    'http://124.93.201.59:42672',
    'http://123.149.137.222:9999',
    'http://60.212.197.155:8060',
    'http://175.44.108.106:9999',
    'http://129.204.29.130:8080',
    'http://163.204.241.204:9999',
    'http://60.167.23.44:9999',
    'http://47.112.222.241:8000',
    'http://223.199.30.80:9999',
    'http://129.204.29.130:8080',
    'http://123.163.27.5:9999',
    'http://118.24.246.249:80',
    'http://218.58.194.162:8060',
    'http://183.166.118.149:9999',
    'http://120.79.193.230:8000',
    'http://118.24.246.249:80',
    'http://1.198.73.9:9999',
    'http://180.118.128.199:9000',
    'http://110.243.31.10:9999',
    'http://39.108.86.7:8000',
    'http://219.146.127.6:8060',
    'http://139.199.219.235:8888',
    'http://120.79.193.230:8000',
    'http://120.79.193.230:8000',
    'http://36.249.48.55:9999',
    'http://175.44.108.55:9999',
    'http://110.189.152.86:43164',
]


# :)
__cookies__ = {'JSESSIONID': '3708E838E06CDA41A96B3A9F209A2978'}


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
                    async with sess.get(url, proxy=self.proxy, timeout=timeout, cookies=__cookies__) as resp:
                        headers = resp.headers
                        # print(headers)
                        if (
                            int(headers['X-PropertyRateLimiting-Remaining-Hour']) < 10
                            or int(headers['X-PropertyRateLimiting-Remaining-Minute']) < 10
                            or int(headers['X-PropertyRateLimiting-Remaining-Day']) < 10
                        ):
                            raise Retry
                        html = await resp.text()
                        return resp, resp.headers, html
            except Exception as e:
                print(f'request got error: {e} {type(e)}')
                self.switch_proxy()

    async def get_article(self, year, month, day, face, hash):
        title_pattern = re.compile(r'<div class="title">(.*?)</div>')
        subtitle_pattern = re.compile(r'<div class="subtitle">(.*?)</div>')
        author_pattern = re.compile(r'<div class="author">(.*?)</div>')
        # title_pattern = re.compile(r'<div class="title">(.*?)</div>')
        article_info_pattern = re.compile(
            r'<div class="sha_left">.*?【人民日报<span>([\d\-]+)</span>\s+第<span>(\d+)</span>版\s+(<span>(.*?)</span>)?.*?</div>',
            re.MULTILINE | re.DOTALL,
        )
        content_pattern = re.compile(
            r'<div id="FontZoom"\s+class="detail_con">\s+(.*?)\s+</div>', re.MULTILINE | re.DOTALL
        )

        url = f'http://data.people.com.cn/rmrb/{year:02d}{month:02d}{day:02d}/{face}/{hash}'
        # url = 'http://data.people.com.cn/rmrb/20190430/11/d597efcbc59a4c3b8f005529649e230b'
        resp, _, html = await self.request(url)
        if resp.url != url:
            print('url mismatch')
            raise SystemExit
        print(html)
        if '<title>未登录</title>' in html:
            print('需要登录')
            raise SystemExit
        try:
            title = title_pattern.findall(html)[0]
            subtitle = (subtitle_pattern.findall(html) + [''])[0]
            author = (author_pattern.findall(html) + [''])[0]
            when_, face_, has_type_, type_ = article_info_pattern.findall(html)[0]
            content = content_pattern.findall(html)[0]
        except Exception as e:
            raise e
        print(title, subtitle, author, when_, type_, content)
        data = {
            'title': title,
            'subtitle': subtitle,
            'author': author,
            'date': when_,
            'type': type_,
            'content': content,
        }
        return data

    async def run_article_download_loop(self):
        task = True
        async with aiohttp.ClientSession(headers=__headers__) as sess:
            while task:
                task = await self.queue.get()
                if not task:
                    print(f'{self.name} DONE!!')
                    return
                year, month, day, face, hash_ = task
                while True:  # error retry loop
                    try:
                        data = await self.get_article(year, month, day, face, hash_)
                        with open(f'data/{year}/{month:02d}/{day:02d}/{face}/{hash_}.json', 'w') as fp:
                            json.dump(data, fp, ensure_ascii=False)
                        break
                    except Retry:
                        self.switch_proxy()
                    except Skip:
                        break
                self.queue.task_done()

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

        meta = dict(year=y, month=m, day=d, nface=total_faces, narticle=total_articles)

        if int(day) != int(d) or int(year) != int(y):
            print(html)
            print(f'{self.name} date error')
            raise Skip

        face_meta = dict(narticle=narticle, articles=articles, sketchpic=sketchpic, type=face_type or '')

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
                return  # this is ok
            else:
                for face in range(2, nface + 1):
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
                        return  # yep
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


async def article_worker(name, queue):
    rmrb = RiRenMinBao(name, queue)
    await rmrb.run_article_download_loop()


async def main():
    queue = asyncio.Queue()
    N = 30
    tasks = []
    for i in range(N):
        task = asyncio.create_task(worker(f'worker-{i+1}', queue))
        tasks.append(task)

    # initial_day = date(1946, 5, 15)
    initial_day = date(2019, 4, 15)
    day = initial_day

    while day <= date.today():
        path = os.path.join(__dir__, f'data/{day.year}/{day.month:02d}/{day.day:02d}')
        # if os.path.exists(path):
        queue.put_nowait((day.year, day.month, day.day))
        day += timedelta(1)

    # queue.put_nowait((1946, 6, 28))

    for i in range(N):
        queue.put_nowait(None)

    await asyncio.gather(*tasks)


async def main_download_articles():
    queue = asyncio.Queue()
    N = 2
    tasks = []
    for i in range(N):
        task = asyncio.create_task(article_worker(f'article-worker-{i+1}', queue))
        tasks.append(task)

    day = date.today()

    while day.year >= 2019:
        path = os.path.join(__dir__, f'data/{day.year}/{day.month:02d}/{day.day:02d}')
        if os.path.exists(f'{path}/1/meta.json'):  # first face
            with open(f'{path}/meta.json') as fp:
                meta = json.load(fp)
                nface = int(meta['nface'])


if __name__ == '__main__':
    asyncio.run(main())
    # asyncio.run(main_download_articles())


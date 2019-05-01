

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


proxy_addrs = """
http://123.206.204.51:8118
http://121.232.194.75:9000
http://121.13.252.62:41564
http://119.145.2.100:44129
http://183.129.207.86:13698
http://121.13.252.62:41564
http://118.181.226.216:58654
http://136.228.128.14:61158
http://60.173.244.133:35634
http://183.129.244.22:13297
http://121.233.207.152:9999
http://60.173.244.133:35634
http://117.131.99.210:53281
http://47.104.172.108:8118
http://47.93.18.195:80
http://114.113.222.132:80
http://60.217.64.237:63141
http://58.48.168.166:51430
http://117.91.254.211:9999
http://117.131.99.210:53281
http://222.135.92.68:38094
http://117.93.81.127:53281
http://47.98.183.137:8082
"""


class RiRenMinBao(object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.proxy_list = list(filter(None, proxy_addrs.split()))
        self.proxies = {}


    def get_page_meta(self, year, month, day, page=1):
        url = "http://data.people.com.cn/rmrb/%d%02d%02d/%d" % (year, month, day, page)

        sess = requests.session()
        sess.headers.update(__headers__)
        resp = sess.get(url, proxies=self.proxies, timeout=(4, 10))
        headers = resp.headers

        if int(headers['X-PropertyRateLimiting-Remaining-Hour']) < 10 or \
                int(headers['X-PropertyRateLimiting-Remaining-Minute']) < 10 or \
                int(headers['X-PropertyRateLimiting-Remaining-Day']) < 10:
            print('too fast and switch proxy')
            print(headers)
            self.switch_proxy()
            raise RuntimeError

        if day == 1:
            print(resp.headers)
        print(resp.url)
        if resp.url != url:
            print('url redirected')
            return None, None

        html = resp.text

        article_part = html.split('class="title_list">')[1].split('class="index_banshi">')[0]

        y, m, d, total_faces, total_articles = date_pattern.findall(html)[0]

        face, has_face_type, face_type, narticle = info_pattern.findall(html)[0]

        articles = article_link_pattern.findall(article_part)
        sketchpic = sketchpic_pattern.findall(html)[0]

        meta = dict(
            year=y,
            month=m,
            day=d,
            nface=total_faces,
            narticle=total_articles,
        )
        print(meta)

        if int(day) != int(d):
            print(html)
            print('date error')
            raise SystemExit

        face_meta = dict(
            narticle=narticle,
            articles=articles,
            sketchpic=sketchpic,
            type=face_type or '要闻',
        )

        for title, link in articles:
            print(">>", title)
        return meta, face_meta

    def switch_proxy(self):
        if self.proxies:
            self.proxy_list.remove(self.proxies['http'])
        if not self.proxy_list:
            print("proxy all used!")
            raise SystemExit
        proxy = random.choice(self.proxy_list)
        print('change proxy=', proxy)
        self.proxies = {
            "http": proxy
        }



    def visit(self, year, month, day):
        path = os.path.join(__dir__, "data/%04d/%02d/%02d" % (year, month, day))

        if os.path.exists(path):
            print(year, month, day, 'skip')
            return

        try:
            meta, face_meta = self.get_page_meta(year, month, day)
            assert meta, ""
        except IndexError as e:
            traceback.print_exc()
            print('error! skip')
            return
        except AssertionError:
            print('assert page error')
            return
        except (requests.Timeout, requests.ConnectionError, RuntimeError, requests.exceptions.ChunkedEncodingError) as e:
            print(f'error={type(e)}! change proxy!')
            self.switch_proxy()
            return self.visit(year, month, day)
        except Exception as e:
            print(e, type(e))
            raise e



        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "meta.json"), 'w') as fp:
            json.dump(meta, fp, ensure_ascii=False)

        os.makedirs(os.path.join(path, "1"))
        with open(os.path.join(path, "1", "meta.json"), 'w') as fp:
            json.dump(face_meta, fp, ensure_ascii=False)

        return True


def extract_info_from_html(html):
    pass

"""
X-Propertyratelimiting-Remaining-Second
199
X-Propertyratelimiting-Remaining-Minute
398
X-Propertyratelimiting-Remaining-Hour
1998
X-Propertyratelimiting-Remaining-Day
5998
"""

rmrb = RiRenMinBao()


initial_day = date(1945, 5, 15)
#initial_day = date(2012, 7, 1)

day = initial_day
while True:
    print(day)
    rmrb.visit(day.year, day.month, day.day)
    day += timedelta(1)
    # input()
    # time.sleep(0.4)
print(initial_day)
# rmrb.visit(1946, 5, 15)

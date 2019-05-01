#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
from urllib import request
import requests

import re
import time
import threading
import asyncio
import aiohttp

socket.setdefaulttimeout(5.0)

WECHAT_UA = "Mozilla/5.0 (Linux; Android 9; TWOPLUS A6010 Build/PKQ1.180716.001; wv) " + \
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/66.0.3359.126 " + \
    "MQQBrowser/6.2 TBS/044607 Mobile Safari/537.36 MMWEBID/4820 MicroMessenger/7.0.4.1420(0x27000439) " + \
    "Process/tools NetType/WIFI Language/ja"

__headers__ = {
    "User-Agent": WECHAT_UA,
}

sess = requests.session()
sess.headers.update(__headers__)


def timestamp():
    return int(time.time())

def timing(func, *args, **kwargs):
    start = time.time()
    ret = func(*args, **kwargs)
    elapsed = time.time() - start
    return (elapsed, ret)

async def fetch_proxy_list(queue):
    print('???')
    urls = ["https://www.kuaidaili.com/free/inha/%s/" % p for p in range(1, 20)]
    pattern = re.compile(r'<tr>(.*?)</tr>', re.DOTALL | re.MULTILINE)
    ip_pattern = re.compile(r'<td data\-title="IP">\s*(\d+\.\d+\.\d+\.\d+)\s*</td', re.DOTALL)
    port_pattern = re.compile(r'<td data\-title="PORT">\s*(\d+)\s*</td', re.DOTALL)
    type_pattern = re.compile(r'<td data\-title="类型">\s*(\w+)\s*</td', re.DOTALL)
    print('....')

    async with aiohttp.ClientSession(headers=__headers__) as sess:
        print('open sess')
        for url in urls:
            print('loading url', url)
            async with sess.get(url) as resp:
                html = await resp.text()
                if len(html) < 100:
                    print('error loading html')
                matches = pattern.findall(html)
                for match in matches:
                    ips = ip_pattern.findall(match)
                    if not ips:
                        continue
                    ports = port_pattern.findall(match)
                    assert len(ips) == len(ports) == 1

                    print('enqueue', ips[0])

                    queue.put_nowait((ips[0], ports[0]))
                await asyncio.sleep(1)
    queue.put_nowait((None, None)) # ends


good_proxy = []


async def verify_proxy(name, queue):
    print('worker start')
    while True:
        ip, port = await queue.get()
        if not ip:
            print('worker ends')
            queue.put_nowait((None, None)) # 2333
            break
        print(name, 'get from queue:', ip, port)
        proxy = f'http://{ip}:{port}'
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            try:
                async with sess.get('http://34.238.32.178/ip', proxy=proxy) as resp:
                    # print(proxy, resp.status)
                    ret = await resp.json()
                    # print(">>>", ret)
                    print(f'http://{ip}:{port}  ok')
                    good_proxy.append(f'http://{ip}:{port}')
                    queue.task_done()
            except Exception as e:
                # print('error', ip, e, type(e))
                pass



async def main():
    queue = asyncio.Queue()

    queue.put_nowait(('127.0.0.1', 1080))

    tasks = []
    for i in range(20):
        task = asyncio.create_task(verify_proxy(f'worker-{i}', queue))
        tasks.append(task)

    main_task = asyncio.create_task(fetch_proxy_list(queue))


    #await queue.join()
    await asyncio.gather(main_task, *tasks)
    print('main ends')



if __name__ == '__main__':
    asyncio.run(main())
    #asyncio.run



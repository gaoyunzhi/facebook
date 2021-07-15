#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
from telegram_util import log_on_fail, matchKey
from telegram.ext import Updater
import plain_db
import cached_url
from bs4 import BeautifulSoup
import album_sender
import time
import facebook_to_album
import facebook_scraper
import plain_db
import random
import time

with open('credential') as f:
    credential = yaml.load(f, Loader=yaml.FullLoader)

with open('db/setting') as f:
    setting = yaml.load(f, Loader=yaml.FullLoader)

existing = plain_db.loadKeyOnlyDB('existing')
tele = Updater(credential['bot_token'], use_context=True)
debug_group = tele.bot.get_chat(credential['debug_group'])
blocklist = plain_db.loadKeyOnlyDB('blocklist')
fetchtime = plain_db.load('fetchtime')

def getKey(url):
    return url.strip('/').split('/')[-1]

def getSchedule():
    schedules = []
    for channel_id, pages in setting.items():
        for page, detail in pages.items():
            schedules.append((fetchtime.get(page, 0), channel_id, page, detail))
    schedules.sort()
    if time.time() - schedules[-1][0] < 30 * 60:
        return
    _, channel_id, page, detail = schedules[0]
    fetchtime.update(page, int(time.time()))
    return tele.bot.get_chat(channel_id), page, detail

@log_on_fail(debug_group)
def run():
    schedule = getSchedule()
    if not schedule:
        print('facebook skip, min_interval: 30 minutes')
        return
    channel, page, detail = schedule
    try:
        posts = facebook_scraper.get_posts(page, pages=10)
    except Exception as e:
        message = 'facebook fetch failed for %s: %s' % (page, e)
        print(message)
        debug_group.send_message(message)
        return
    count = 0
    for post in posts:
        count += 1
        url = post['post_url']
        with open('nohup.out', 'a') as f:
            f.write('%s\n%s\n\n' % (url, str(post)))
        if existing.contain(url):
            continue
        if getKey(url) in [getKey(item) for item in existing._db.items.keys()]:
            continue
        if post['likes'] < detail.get('likes', 100):
            continue
        if matchKey(str(post), blocklist.items()):
            continue
        album = facebook_to_album.get(post, detail)
        try:
            album_sender.send_v2(channel, album)
        except Exception as e:
            print('facebook sending fail', url, e)
            with open('nohup.out', 'a') as f:
                f.write('\n%s %s %s' % (url, str(e), str(post)))
            continue
        existing.add(album.url)
    if count == 0:
        message = 'facebook fetched nothing: %s' % page
        
if __name__ == '__main__':
    run()
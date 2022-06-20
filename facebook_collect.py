#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
from telegram_util import log_on_fail, matchKey, isCN
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
import warnings
warnings.filterwarnings('ignore')

GAP_MIN = 100

with open('credential') as f:
    credential = yaml.load(f, Loader=yaml.FullLoader)

with open('db/setting') as f:
    setting = yaml.load(f, Loader=yaml.FullLoader)

existing = plain_db.loadKeyOnlyDB('existing')
tele = Updater(credential['bot_token'], use_context=True)
debug_group = tele.bot.get_chat(credential['debug_group'])
translate_channel = tele.bot.get_chat(credential['translate_channel'])
blocklist = plain_db.loadKeyOnlyDB('blocklist')
fetchtime = plain_db.load('fetchtime')
stale = plain_db.loadKeyOnlyDB('stale')

def getKey(url):
    return url.strip('/').split('/')[-1]

def getSchedule():
    schedules = []
    include_stale = random.random() < 0.01
    priority_only = random.random() > 0.5
    for channel_id, pages in setting.items():
        for page, detail in pages.items():
            if page in stale.items() and not include_stale:
                continue
            if priority_only and not detail.get('priority'):
                continue
            schedules.append((fetchtime.get(page, 0), channel_id, page, detail))
    schedules.sort()
    if time.time() - schedules[-1][0] < GAP_MIN * 60:
        return
    _, channel_id, page, detail = schedules[0]
    fetchtime.update(page, int(time.time()))
    return tele.bot.get_chat(channel_id), page, detail

@log_on_fail(debug_group)
def run():
    schedule = getSchedule()
    if not schedule:
        print('facebook skip, min_interval: %d minutes' % GAP_MIN)
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
    latest_create_at = 0
    for post in posts:
        count += 1
        url = post['post_url']
        with open('tmp_post', 'w') as f:
            f.write('%s\n%s' % (url, str(post)))
        latest_create_at = max(post['time'].timestamp(), latest_create_at)
        if existing.contain(url):
            continue
        if getKey(url) in [getKey(item) for item in existing._db.items.keys()]:
            continue
        if post['likes'] < detail.get('likes', 100):
            continue
        if matchKey(str(post), blocklist.items()):
            continue
        album = facebook_to_album.get(post, detail)
        if isCN(album.cap_html_v2):
            backup_channel = debug_group
        else:
            backup_channel = translate_channel
        try:
            album_sender.send_v2(channel, album)
            album_sender.send_v2(backup_channel, album.toPlain())
        except Exception as e:
            print('facebook sending fail', url, e)
            with open('tmp_failed_post', 'w') as f:
                f.write('%s %s %s' % (url, str(e), str(post)))
            continue
        existing.add(album.url)
    if count == 0:
        message = 'facebook fetched nothing: %s' % page
    if latest_create_at != 0:
        if time.time() - latest_create_at > 60 * 24 * 60 * 60:
            stale.add(page)
        else:
            stale.remove(page)

if __name__ == '__main__':
    run()
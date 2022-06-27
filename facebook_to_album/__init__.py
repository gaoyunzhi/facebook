#!/usr/bin/env python3
# -*- coding: utf-8 -*-

name = 'facebook_to_album'

from telegram_util import AlbumResult as Result
import hanzidentifier
from telegram_util import isCN
from opencc import OpenCC

cc = OpenCC('tw2sp')

def dedup(images):
	exist = set()
	for image in images:
		if not image:
			continue
		if image in exist:
			continue
		if 'p32x32' in image:
			continue
		exist.add(image)
		yield image

def getText(text, comment, link):
	if link:
		return text + '\n\n' + link
	if not comment or text == comment:
		return text
	index = comment.find('\n\n')
	if index == -1:
		return text
	comment = comment[index:].strip()
	if len(comment) < 10:
		return text
	if not text:
		return comment
	return text + '\n\ncomment: ' + comment
	
def dedupText(text):
	# fix to the library's bug
	existing = set()
	result = []
	for line in text.split('\n'):
		if not line: 
			result.append(line)
			continue
		if line in existing:
			return '\n'.join(result).strip().replace('\n\n\n', '\n\n')
		existing.add(line)
		result.append(line)
	return '\n'.join(result).strip().replace('\n\n\n', '\n\n')

def shouldSimplify(text):
	for c in text:
		if isCN(c) and not hanzidentifier.is_simplified(c):
			return True
	return False

def simplify(text):
	if shouldSimplify(text):
		return cc.convert(text)
	return text

def get(content, setting):
    result = Result()
    result.url = content['post_url']
    result.video = content['video']
    result.cap_html_v2 = simplify(dedupText(getText((content['post_text'] or '').strip(), content['shared_text'], content.get('link'))))
    result.imgs = list(dedup(content['images'] or content['images_lowquality'] or []))
    if result.imgs and result.imgs[0].startswith('https://m.facebook.com/photo/view_full_size'):
    	result.imgs = list(dedup(content['images_lowquality'] or []))
    if setting.get('prefix'):
    	result.cap_html_v2 = setting.get('prefix') + result.cap_html_v2
    if content.get('listing_price'):
    	result.cap_html_v2 += '\n\n【价格】%s\n【邮编】%s\n【联系】%s' % (
    		content.get('listing_price'), content.get('listing_location'), content.get('post_url'))
    return result
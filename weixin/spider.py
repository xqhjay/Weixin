# !/usr/bin/env python
# !-*-coding:utf-8 -*-
# !@Author : xuqh
# !@Email  : xqhjay@foxmail.com
# !@File   : spider.py
import pymongo
from weixin.config import *
from urllib.parse import urlencode
import requests
from pyquery import PyQuery as pq
from requests import ConnectionError, ReadTimeout


class Spider():
    client = pymongo.MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    base_url = 'http://weixin.sogou.com/weixin?'
    headers = {
        'Connection': 'keep - alive',
        'Cookie': 'IPLOC=CN4201; SUID=D37E71DCB437990A000000005ADDFE78; SUV=004C253BDC717ED35ADDFE7BAFD53530; ABTEST=0|1527936696|v1; weixinIndexVisited=1; LSTMV=338%2C175; LCLKINT=14565; PHPSESSID=l2t43q55ponacjubivivp7baf3; SUIR=BB5957FB262248CCB2FC0C452777D572; JSESSIONID=aaaDSKVw71OxE95jolnnw; ppinf=5|1529334766|1530544366|dHJ1c3Q6MToxfGNsaWVudGlkOjQ6MjAxN3x1bmlxbmFtZTo1NDolRTYlOTclQjYlRTklOTclQjQlRTYlOUYlOTMlRTQlQjglOEElRTclQTklQkElRTclOTklQkR8Y3J0OjEwOjE1MjkzMzQ3NjZ8cmVmbmljazo1NDolRTYlOTclQjYlRTklOTclQjQlRTYlOUYlOTMlRTQlQjglOEElRTclQTklQkElRTclOTklQkR8dXNlcmlkOjQ0Om85dDJsdUs3SDZvOHdRVGg4b2tYakZLVE9xSmdAd2VpeGluLnNvaHUuY29tfA; pprdig=lVNivBT89OhQ_4GtkFXQlUMyzty2Hp0Tck7TSHdUmEX26y3g36-6omeKiPceH_6KsQicfr9NCLchNZAz8pHKOXn2isKZgorjBal_3Rzikrjz5pfXSFtwQAZlGgl9dLqQOWbpxh9_xRf8xIJ2uCZcv_TLVjFcmlsnWn4FKhzp9LE; sgid=24-35323937-AVsnyib4osccjYeT8JsWGT7U; SNUID=62808F22FDFB90105FFDE9CCFEF6F6F0; session_id_crm-bo=crm-bo_b4ae4031-f037-4cdc-b552-721583355057; ppmdig=1529563754000000c0335ae7388d52ed0963d382bba75d9e; sct=13',
        'Host': 'weixin.sogou.com',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
    }
    proxy = None
    session = requests.session()
    session.headers.update(headers)

    def get_proxy(self):
        """
        从代理池获取代理
        :return:
        """
        try:
            response = requests.get(PROXY_POOL_URL)
            if response.status_code == 200:
                print('Get Proxy', response.text)
                return response.text
            else:
                return None
        except requests.ConnectionError:
            return None

    def get_index(self, keyword, page):
        data = {'query': keyword,
                'type': 2,
                'page': page
                }
        queries = urlencode(data)
        url = self.base_url + queries
        html = self.get_html(url)
        return html

    def get_html(self, url, count=1):
        """
        初始化工作
        """
        # 全局更新Headers

        print('正在抓取：', url)
        print('尝试次数：', count)
        if count >= MAX_FAILED_TIME:
            print('Tried Too Many Counts')
            return None
        try:
            if self.proxy:
                proxies = {
                    'http': 'http://' + self.proxy,
                    'https': 'https://' + self.proxy
                }
                response = self.session.get(url, timeout=TIMEOUT, allow_redirects=False, proxies=proxies)
            else:
                response = self.session.get(url, timeout=TIMEOUT, allow_redirects=False)
            # print('response.status_code:', response.status_code)
            if response.status_code == 200:
                print('200')
                print(response.text)
                return response.text
            if response.status_code == 302:
                print('302')
                self.proxy = self.get_proxy()
                if self.proxy:
                    print('获取的代理为:', self.proxy)
                    return self.get_html(url)
                else:
                    print('获取代理失败！')
                    return None
        except (ConnectionError, ReadTimeout) as e:
            print('Error Occurred', e.args)
            self.proxy = self.get_proxy()
            count += 1
            return self.get_html(url, count)

    def parse_index(self, html):
        """
        解析索引页
        :param response: 响应
        :return: 新的响应
        """
        doc = pq(html)
        items = doc('.news-box .news-list li .txt-box h3 a').items()
        for item in items:
            yield item.attr('href')

    def get_detail(self, url):
        """
        解析详情页
        :param url: 文章链接
        :return: 文章网页
        """
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.text
        except ConnectionError as e:
            print(e.args)
            return None

    def parse_detail(self, html):
        """
        解析详情页
        :param html: 文章网页
        :return: 微信公众号文章
        """
        doc = pq(html)
        data = {
            'title': doc('.rich_media_title').text(),
            'content': doc('.rich_media_content').text(),
            'date': doc('#post-date').text(),
            'nickname': doc('#js_profile_qrcode > div > strong').text(),
            'wechat': doc('#js_profile_qrcode > div > p:nth-child(3) > span').text()
        }
        return data

    def save_to_mongo(self, data):
        if self.db['articles'].update({'title': data['title']}, {'$set': data}, True):
            print('存储到ongodbM!', data['title'])
        else:
            print('存储到Mongodb失败!', data['title'])

    def run(self):
        """
        入口
        :return:
        """
        for page in range(1, 100):
            html = self.get_index(KEYWORD, page)
            if html:
                article_urls = self.parse_index(html)
                for article_url in article_urls:
                    print(article_url)
                    article_html = self.get_detail(article_url)
                    if article_html:
                        article_data = self.parse_detail(article_html)
                        print(article_data)
                        self.save_to_mongo(article_data)


if __name__ == '__main__':
    spider = Spider()
    spider.run()

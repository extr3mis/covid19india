# bot.py

import os
import json
import requests
import time
import datetime
import threading

from abc import ABC, abstractmethod

import tweepy
from tweepy import TweepError

with open('url_keys.json') as fp:
    BITLY_API_KEY = json.load(fp)['api_key']


class API(ABC):
    """
    The Abstract Base Class for API classes.
    """
    @abstractmethod
    def get():
        return


class ABCBot(ABC):

    @abstractmethod
    def create_api(self):
        return None

    @abstractmethod
    def tweet(self):
        return None


class Bot:
    def __init__(self, keyfile: str):
        """
        Creates a `Twitter` object to interact with the Twitter API. Built on top of `tweepy`'s API class for convenience.

        `keyfile`: The path to the `keys.json` file.

        """

        self.api = self.create_api(keyfile)
        self.me = self.api.me()

    def create_api(self, keyfile: str):
        """
        Creates the `tweepy.API` object required to interact with twitter.

        `keyfile`: The path to the `keys.json` file.
        """

        with open(keyfile, 'r') as fp:
            keys = json.load(fp)

        auth = tweepy.OAuthHandler(
            keys['consumer_key'], keys['consumer_secret'])

        auth.set_access_token(keys['access_token_key'],
                              keys['access_token_secret'])

        api = tweepy.API(auth)

        try:
            api.verify_credentials()

        except Exception as e:
            print(f'{type(e).__name__}: {e}')

        return api

    def tweet(self, text, **kwargs):
        """
        Posts a tweet to the authenticated account. Returns `True` if successful.
        Supported keyword arguments:
        image: url of an online image file.
        """

        if 'image' in kwargs.keys():
            with open(f'temp.{kwargs["image"].split(".")[-1]}', 'wb') as img:
                response = requests.get(kwargs['image'])
                img.write(response.content)

            image = self.api.media_upload(
                f'temp.{kwargs["image"].split(".")[-1]}')
            try:
                self.api.update_status(text, media_ids=[image.media_id])
            except TweepError:
                pass

            os.remove(f'temp.{kwargs["image"].split(".")[-1]}')
        else:
            try:
                self.api.update_status(text)
            except TweepError:
                pass


class CoronaAPI(API):
    def __init__(self):
        """
        The interface for interacting with the COVID-19 API to get information from MOHFW.
        """
        self.URL = 'https://api.apify.com/v2/key-value-stores/toDWvRj1JpTXiM8FF/records/LATEST?disableRedirect=true'

    def get(self):
        """
        Gets a response from the API.
        """
        with requests.get(self.URL) as rp:
            response = rp.json()
        return response


class Task(threading.Thread):
    def __init__(self, **kwargs):
        """
        Creates a repeating, periodic, background `Task` object. Accepts a "task" function and a sleep interval as keyword arguments/
        """
        super().__init__()

        self.running = True
        self.killed = False

        try:
            self.task = kwargs['task']
        except:
            raise RuntimeError('Task function not specified')

        try:
            self.sleep = kwargs['sleep']
        except:
            raise RuntimeError('Sleep period missing')

    def run(self):
        """
        Overriding the internal `run()` method of a threading.Thread() object.
        """
        while not self.killed:
            if self.running:
                self.task()
                time.sleep(self.sleep)

    def stop(self):
        """
        Pauses the `Task` loop.
        """
        self.running = False

    def restart(self):
        """
        Restarts a paused `Task`.
        """
        self.running = False
        self.running = True

    def kill(self):
        """
        Kills and finally ends the `Task` loop.
        """
        self.stop()
        self.killed = True
        self.join()


class NewsAPI(API):
    def __init__(self, keyfile):
        """
        API interface to the NEWSAPI service.

        `keyfile`: The `json` file containing the API key.
        """

        super().__init__()
        self.URL = 'https://newsapi.org/v2/top-headlines'
        with open(keyfile, 'r') as fp:
            self.key = json.load(fp)['api_key']

    def get(self, **params):
        """
        The `GET` HTTP call to the API. Takes many search queries as keyword arguments. Returns a `dict` object.
        """ 

        params.update({'apiKey': self.key})
        x = params.pop('start', False)
        if x:
            params.update({'from': x})
        with requests.get(self.URL, params=params) as response:
            r = response.json()
            if response.status_code in range(200, 300):
                return r
            else:
                raise RuntimeError(
                    f'Response raised error: {response.status_code}\n{r["message"]}')


class Helpers:
    """
    Helper class for tasks that might require shorthands.
    """

    @staticmethod
    def today():
        return datetime.date.today().isoformat()

    @staticmethod
    def yesterday():
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        return yesterday.isoformat()


class Short:
    """
    URL shortener interface. Quickly shortens links using the `bit.ly` API.

    `url`: The url to shorten.
    """
    def __init__(self, url: str):
        headers = {'Content-Type': 'application/json',
                   'Authorization': f'Bearer {BITLY_API_KEY}'}

        payload = {
            'domain': 'bit.ly',
            'long_url': url
        }
        with requests.post('https://api-ssl.bitly.com/v4/shorten', json=payload, headers=headers) as r:
            if r.status_code in range(200, 300):
                self.url = r.json()['link']
            else:
                raise RuntimeError(
                    f'bit.ly returned status code {r.status_code}:\n{r.json()}')

    def __str__(self):
        """
        Allows for quick inline shortening.
        """
        return self.url


def daily_stats():
    """
    The task function to post the daily COVID-19 numbers. Needs to be called every 24h.
    """
    response = covid_api.get()
    tweet = f'''In the past 24h, we had:\n{response['activeCasesNew']} new COVID-19 cases.\n{response['recoveredNew']} people recovered.\n{response['deathsNew']} people died of COVID-19.\n\n#COVID #corona #COVID19 #covidindia'''
    bot.tweet(tweet)


def news():
    """
    The task function to post a news story every 2h.
    """
    try:
        response = news_api.get(country='in', q='covid',
                                sortBy='publishedAt',
                                start=Helpers.yesterday())
        n = 0
        flag = False #This ensures stories are never repeated
        while not flag:
            story = response['articles'][n]
            url = str(Short(story['url']))
            
            with open('urls.txt', 'r') as f:
                urls = [x.strip() for x in f.readlines()]
            
            if url in urls:
                n+=1
            else:
                tweet = f'''{story['title']}\nRead full story: {url}\n#COVID #corona #COVID19 #covidindia'''
                try:
                    bot.tweet(tweet, image=story['urlToImage'])
                except FileNotFoundError:
                    n+=1
                    continue
                urls.append(url+'\n')
                with open('urls.txt', 'w') as f:
                    f.write('''
                    '''.join(urls))
                flag = True

    except Exception as e:
        print(f'{type(e).__name__}: {e}')


bot = Bot('twitter_keys.json')
covid_api = CoronaAPI()
news_api = NewsAPI('news_keys.json')

news_task = Task(task=news, sleep=7200)
stats_task = Task(task=daily_stats, sleep=86400)

news_task.start()
stats_task.start()
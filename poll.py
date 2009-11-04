#!/usr/bin/env python

import datetime
import logging
import re
import simplejson
import time
import urllib

import twython

from gqlencoder import GqlEncoder
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import urlfetch

class TweetUser(db.Model):
  ref_id = db.IntegerProperty()
  uid = db.IntegerProperty()
  location = db.StringProperty()
  geo = db.GeoPtProperty()

class Tweet(db.Model):
  user = db.ReferenceProperty(TweetUser, collection_name="tweets")
  id = db.IntegerProperty()
  uid = db.IntegerProperty()
  text = db.StringProperty(multiline=True)
  time = db.TimeProperty()

class PollHandler(webapp.RequestHandler):
  
  def __init__(self):
    self.twitter = twython.setup()
    
  def get(self):
    flush = self.request.get("flush")
    if flush == "true":
      self.flush_all()
    # self.flush_all()
    results = self.get_search("underthehood")
    self.update_twitter_locations()
    self.update_geocoded_locations()
    # only get users with geo information
    result = db.GqlQuery("SELECT * FROM Tweet");
    logging.info("number of tweets: %s" % results.count())
    # for tweet in results:
    #       logging.info("tweet user: %s" % tweet.user)
    
    self.response.headers['Content-Type'] = 'application/json'
    self.response.out.write(GqlEncoder().encode(result))
  
  def flush_all(self):
    logging.warn("flushing data!")
    memcache.delete("underthehood")
    self.clear_tweet()
    self.clear_tweet_user()
    
  def update_geocoded_locations(self):
    tweet_users = db.GqlQuery("SELECT * FROM TweetUser")
    logging.info("have num users: %s", tweet_users.count())
    for tweet_user in tweet_users:
      logging.info("checking geo: %s for location %s", tweet_user.geo, tweet_user.location)
      if tweet_user.geo is None:
        self.query_geo_location(tweet_user)
      else:
        logging.info("have geo: %s", tweet_user.geo)
  
  def query_geo_location(self, tweet_user):
    
    # prepare the location, search for coordinates
    m = re.findall("-?\d+.\d+,\-?\d+.\d+", tweet_user.location)
    
    if len(m) > 0:
      enc_location = m[0]
    else:
      enc_location = tweet_user.location
      
    try:
      enc_location = urllib.quote(enc_location)
    except:
      # probably has bad characters in it
      return;
      
    # logging.debug("trying to quote this: %s" % enc_location)
    url = "http://maps.google.com/maps/geo?q=%s&output=json&oe=utf8&sensor=true_or_false&key=" % enc_location
    result = urlfetch.fetch(url)
    #logging.info("result code: %s, for location: %s", result.status_code, enc_location)
    logging.info("result status for query_geo_location: ")
    if result.status_code == 200:
      location = simplejson.loads(result.content)
      coordinates = []
      try:
        coordinates = location["Placemark"][0]["Point"]["coordinates"]
        logging.info("coordinates: %s, for: %s", coordinates, tweet_user.location)
      except:
        logging.info("was not able to find location for: %s" % tweet_user.location)
      if len(coordinates) > 0: # for some reason, we have to switch from lon,lat
        tweet_user.geo = "%(a)s,%(b)s" % {'a': str(coordinates[1]), 'b': str(coordinates[0])}
        db.put(tweet_user)
    
    
  def update_twitter_locations(self):
    # can probably be updated to select * from tweetuser where location is none
    tweet_users = db.GqlQuery("SELECT * FROM TweetUser")
    for tweet_user in tweet_users:
      if tweet_user.location is None:
        self.query_location(tweet_user)

    # tweet_users2 = db.GqlQuery("SELECT * FROM TweetUser")
    #     for tweet_user2 in tweet_users2:
    #       self.response.out.write(" >> user id: " + str(tweet_user2.uid) + ", location: " + str(tweet_user2.location)  + "   |    ")
    
  def query_location(self, tweet_user):
    mem_key = str(tweet_user.ref_id)
    location = memcache.get(mem_key)
    if location is None:
      try:
        # try getting their status message. it could potentially be blocked
        result = self.twitter.showStatus(tweet_user.ref_id)
        location = result["user"]["location"]
      except:
        location = None
      logging.info("querying twitter location for user: %s" % tweet_user.uid)
      if location is None:
        location = "None"
      if not memcache.add(mem_key, location, 86400): # cache this for one day
        logging.error("memcache failed on query_location")

    tweet_user.location = location
    db.put(tweet_user)
    
  """ search twitter for a search term, cached every 3 minutes based on the query """  
  def get_search(self, terms):
    tweets = memcache.get(terms)
    # tweets = None
    if tweets is not None:
      logging.info("using cached results for get_search")
      return tweets
    else:
      logging.info("get_search results timed out, querying twitter")
      tweets = self.query_search(terms)
      if not memcache.add(terms, tweets, 180): 
        logging.error("memcache failed on get_search")
      logging.info("have %s new tweets" % tweets.count())
      return tweets
      
  """ does the actual API query"""
  def query_search(self, terms):
    tweets = db.GqlQuery("SELECT * FROM Tweet")
    try:
      search_results = self.twitter.searchTwitter(terms, rpp="100")
    except:
      logging.error("searchTwitter API call failed")
    try:
      for tweet in search_results["results"]:
        tweet_id = tweet["id"];
        tweet_uid = tweet["from_user_id"]
        tweet_text = tweet["text"].replace('"', '\"')
        # if this is a new user, add it to our TweetUser table
        db_tweet_user = db.GqlQuery("SELECT * FROM TweetUser WHERE uid = :1", tweet_uid)
        if db_tweet_user.count() == 0:
          tweet_user = TweetUser(ref_id=tweet_id,
                                 uid=tweet_uid,
                                 location=None,
                                 geo=None)
          db.put(tweet_user)
        
        result = db.GqlQuery("SELECT * FROM TweetUser WHERE uid = :1", tweet_uid)
        tweet_user = result[0]
          
        # dont add duplicate tweets
        db_tweet = db.GqlQuery("SELECT * FROM Tweet WHERE id = :1", tweet_id)
        if db_tweet.count() == 0:
          tweet = Tweet(user=tweet_user,
                        id=tweet_id,
                        uid=tweet_uid,
                        text=tweet_text,
                        time=None)
          db.put(tweet)
    except Exception:
      logging.error("an error has occured with query_search")
                         
    return db.GqlQuery("SELECT * FROM Tweet")
  
  def clear_tweet(self):
    q = db.GqlQuery("SELECT * FROM Tweet")
    if q.count() != 0:
      for result in q:
        db.delete(result)
        
  def clear_tweet_user(self):
    q = db.GqlQuery("SELECT * FROM TweetUser")
    if q.count() != 0:
      for result in q:
        db.delete(result)
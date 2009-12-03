import datetime
import time

from poll import Tweet
from poll import TweetUser
from google.appengine.ext import db
from google.appengine.ext import webapp

class StatsHandler(webapp.RequestHandler):
  
  def get(self):
    t1 = self.mktime(2009, 11, 8, 1, 0, 0, 0)
    t2 = self.mktime(2009, 11, 8, 2, 15, 0, 0)
    
    t3 = self.mktime(2009, 11, 8, 1, 30, 0, 0)
    t4 = self.mktime(2009, 11, 8, 2, 15, 0, 0)
    
    tweets = self.getAll(Tweet)
    tweetUsers = self.getAll(TweetUser)
    
    tweetsDuring = self.getTweetsBetween(t3, t4, tweets)
    tweetsDuringAll = self.getTweetsBetween(t1, t2, tweets)
    
    self.getTopLocations(tweetUsers)

    self.response.headers['Content-Type'] = 'text/html'    
    self.response.out.write("total number of tweets: %s<br/>" % len(tweets))
    self.response.out.write("total unique twitter users: %s<br/>" % len(tweetUsers))
    self.response.out.write("number of tweets between 5pm and 7:30pm: %s<br/>" % len(tweetsDuringAll))
    self.response.out.write("number of tweets between 5:30pm and 6:15pm: %s<br/>" % len(tweetsDuring))

  def getTopLocations(self, users):
    locMap = {}
    for user in users:
      try:
        locMap[user.location] += 1
      except:
        locMap[user.location] = 1
    for loc in locMap:
      self.response.out.write("have location: %(l)s with %(n)s tweets<br/>" % {"l": loc, "n": locMap[loc]})
      
      
  def mktime(self, year, month, day, hour, minute, second, microsecond):
    d = datetime.datetime(year, month, day, hour, minute, second, microsecond)
    return time.mktime(d.timetuple())
    
  def getAll(self, dbType):
    q = dbType.all()
    results = []
    for result in q:
      results.append(result)
    return results
    
  def getTweetsBetween(self, time1, time2, tweets):
    between = []
    for tweet in tweets:
      target = time.mktime(tweet.time.timetuple())
      if time1 <= target and target <= time2:
        between.append(tweet)
    return between
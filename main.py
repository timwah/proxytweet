#!/usr/bin/env python

import logging
import wsgiref.handlers

from google.appengine.ext import webapp
from poll import PollHandler
from stats import StatsHandler

class MainHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write('Hello world!')


def main():
  application = webapp.WSGIApplication([('/', MainHandler),
                                        ('/poll', PollHandler),
                                        ('/stats', StatsHandler)],
                                       debug=True)
                                       
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()

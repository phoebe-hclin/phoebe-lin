import webapp2
import jinja2
import os
import re
import hmac
import urllib
from google.appengine.api import memcache
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = False)
secret = 'illbethereforyou'

def render_str(template, **params):
  t = jinja_env.get_template(template)
  return t.render(params)

def make_secure_val(val):
  return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
  val = secure_val.split('|')[0]
  if secure_val == make_secure_val(val):
      return val

##### The base Page Handler class
class WebHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)
    
    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)
    
    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))
    
    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))
    
    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))

      
##### home page handlers
class IndexHandler(WebHandler):
    def get(self):
        self.render("profile.html", loadprofile = True)
        return

class ProfileHandler(WebHandler):
    def get(self):
        self.render("profile.html", loadprofile = True)
        return

class WorkHandler(WebHandler):
    def get(self):
        self.render("work.html", loadwork = True)
        return

class BlogHandler(WebHandler):
    def get(self):
        self.render("blog.html", loadblog = True)
        return

class BlobServe(WebHandler, blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, resource):
        resource = str(urllib.unquote(resource))
        blob_info = blobstore.BlobInfo.get(resource)
        self.send_blob(blob_info)

app = webapp2.WSGIApplication([('/work/?', WorkHandler),
                            ('/profile/?', ProfileHandler),
                            ('/media/([^/]+)?', BlobServe),
                            ('/?', IndexHandler),
                            ],
                            debug=True)
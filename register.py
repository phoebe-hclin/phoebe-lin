import webapp2
import jinja2
import os
import re
import hmac

from models import *

from google.appengine.ext import db
from google.appengine.api import memcache

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = False)

secret = 'mrcuriosity'

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    return password and PASS_RE.match(password)

EMAIL_RE = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)

##### The base Page Handler class
class PageHandler(webapp2.RequestHandler):
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

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))

#Login
class LoginHandler(PageHandler):
    def get(self):
        self.render('login.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        u = User.login(username, password)
        if u:
            self.login(u)
            last_url = self.read_secure_cookie('last_page')
            if last_url:
                self.redirect(str(last_url))
            else:
                self.redirect("/")
        else:
            msg = 'Invalid login'
            self.render('login.html', error = msg)

#Logout
class LogoutHandler(PageHandler):
    def get(self):
        self.logout()
        last_url = self.read_secure_cookie('last_page')
        if last_url:
            self.redirect(str(last_url))
        else:
            self.redirect("/")

#Signup
class SignupHandler(PageHandler):
    isAdmin = False
    def get(self):
        self.render("signup.html")
    def validate(self, username, password, verify, email):
        have_error = False
        params = dict(username = self.username,
      		             email = self.email)
        if not valid_username(self.username):
            params['error_username'] = "That's not a valid username."
            have_error = True
        if not valid_password(self.password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True

        if not valid_email(self.email):
            params['error_email'] = "That's not a valid email."
            have_error = True
        return have_error
    def post(self):
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')
        self.role = None
	    
        if self.validate(self.username, self.password, self.verify, self.email):
            self.render('signup.html', **params)
        else:
            self.done()
    def done(self, *a, **kw):
        #make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('signup.html', error_username = msg)
        else:
            u = User.register(self.username, self.password, self.email, self.role)
            u.put()
            self.login(u)
            last_url = self.read_secure_cookie('last_page')
            if last_url:
                self.redirect(str(last_url))
            else:
                self.redirect("/")
class SignupAdminHandler(SignupHandler):
    def post(self):
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')
        self.role = 1
	    
        if self.validate(self.username, self.password, self.verify, self.email):
            self.render('signup.html', **params)
        else:
            self.done()
        

PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'
app = webapp2.WSGIApplication([('/signup/?', SignupHandler),
                                ('/signupadmin/?', SignupAdminHandler),
                                ('/login/?', LoginHandler),
                                ('/logout/?', LogoutHandler)
                                ],
                                debug=True)
import os
import re
import hmac
import quopri
import logging
from models import *

import webapp2
import jinja2
import datetime
import time
from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import memcache
from google.appengine.runtime import apiproxy_errors

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = False)

class Pacific_tzinfo(datetime.tzinfo):
    """Implementation of the Pacific timezone."""
    def utcoffset(self, dt):
        return datetime.timedelta(hours=-8) + self.dst(dt)

    def _FirstSunday(self, dt):
        """First Sunday on or after dt."""
        return dt + datetime.timedelta(days=(6-dt.weekday()))

    def dst(self, dt):
        # 2 am on the second Sunday in March
        dst_start = self._FirstSunday(datetime.datetime(dt.year, 3, 8, 2))
        # 1 am on the first Sunday in November
        dst_end = self._FirstSunday(datetime.datetime(dt.year, 11, 1, 1))

        if dst_start <= dt.replace(tzinfo=None) < dst_end:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(hours=0)
    def tzname(self, dt):
        if self.dst(dt) == datetime.timedelta(hours=0):
            return "PST"
        else:
            return "PDT"

def utc_to_local(value, format = "%H:%M %Z %B %d, %Y"):
    return datetime.datetime.fromtimestamp(time.mktime(value.timetuple()), Pacific_tzinfo()).strftime(format)

jinja_env.filters['ToLocalTime'] = utc_to_local

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

class BlogHandler(webapp2.RequestHandler):
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

#### memcache ####
def top_posts(limit = 10, update = False):
    key = 'top_posts'
    posts = memcache.get(key)
    if posts is None or update:
        posts = Post.by_created(limit)
        memcache.set(key, posts)
    return posts

def single_post(post_id, update = False):
    key = 'post_' + str(post_id)
    post = memcache.get(key)
    if post is None or update:
        post = Post.by_id(post_id)
        memcache.set(key, post)
    return post

def posts_by_category(cat, update = False):
    key = 'posts_by_category_' + str(cat)
    posts = memcache.get(key)
    if posts is None or update:
        posts = Post.by_category(cat)
        memcache.set(key, posts)
    return posts

def top_comments(limit = 10, update = False):
    key = 'top_comments'
    comments = memcache.get(key)
    if comments is None or update:
        comments = Comment.by_created(limit)
        memcache.set(key, comments)
    return comments

def comments_by_post(post_id, update = False):
    key = 'comments_by_post_' + str(post_id)
    comments = memcache.get(key)
    if comments is None or update:
        comments = Comment.by_post(post_id)
        if len(comments) > 20:
            memcache.set(key, comments[:20])
        else:
            memcache.set(key, comments)
    return comments

def popular_posts(limit = 10, update = False):
    key = 'popular_posts'
    views = memcache.get(key)
    if views is None or update:
        views = View.by_viewcount(limit)
        memcache.set(key, views)
    return views

####

def get_view_count(post_id):
    return View.increment_count(post_id).count

def update_memcache(post_id = -1):
    if post_id != -1:
        single_post(post_id, True)
        comments_by_post(post_id, True)
    top_posts(10, True)
    top_comments(10, True)

### DEBUG: CLEAR EMPTY COMMENT ####
def CLEAR_EMPTY_COMMENTS():
    Comment.delete_all_with_empty_content()
    
#### various blog handler ####
class BlogFront(BlogHandler):
    def get(self):
        try:
            try:
                CLEAR_EMPTY_COMMENTS()
                update_memcache()
            except:
                logging.error('Delete all comments with empty content failed.')

            posts = top_posts()
            comments = top_comments()
            views = popular_posts()
            self.render('blog.html', loadblog = True, posts = posts, recentposts = posts, recentcomments = comments, viewcount = get_view_count('-1'), popularposts = views )
        except apiproxy_errors.OverQuotaError, message:
            logging.error(message)
            self.render('error.html')

class BlogFrontNext(BlogHandler):
    def get(self, page_id):
        self.render('blog.html', loadblog = True)
        
class PostPage(BlogHandler):
    def get(self, post_id):
        try:
            post = single_post(post_id)
        except apiproxy_errors.OverQuotaError, message:
            logging.error(message)
            self.render('error.html')
            return
        
        comments = comments_by_post(post_id, True)
        if not comments:
            comments = []
        recentcomments = top_comments(10, True)
        posts2 = top_posts(10)
        views = popular_posts(10, True)
        self.render("blog_post.html", loadblog = True, post = post, comments = comments, recentposts = posts2, recentcomments = recentcomments, viewcount=get_view_count(post_id), popularposts = views)
    def post(self, post_id):
        post = single_post(post_id)
        if not post:
            self.error(404)
            return
        username = self.request.get('username')
        email = self.request.get('email')
        content = self.request.get('content')

        if username and content and len(content.strip()) != 0:
            c = Comment.save(post_id, username, content, email)
            count = 0
            if post.comment_count:
                count = post.comment_count
            post.update_comment_count(post_id, count+1) 
        
            update_memcache(post_id)

            self.redirect('/blog/%s' % post_id)
        else:
            error = "username and/or content, please!"
            self.render("blog_post.html", loadblog = True, post = post, username = username, email = email, content = content, error = error)

class EditPostPage(BlogHandler):
    def get(self, post_id):
        post = single_post(post_id)
        if not post:
            self.error(404)
            return
        posts2 = top_posts()
        comments = top_comments()
        upload_url = blobstore.create_upload_url('/blog/upload/'+post_id)
        views = popular_posts()
        self.render("blog_newpost.html", loadblog = True, subject = post.subject, content = post.content, category = post.category, recentposts = posts2, recentcomments = comments, viewcount = get_view_count('-1'), uploadurl = upload_url, popularposts = views)

class NewPost(BlogHandler):
    def get(self):
        if self.user:
            if self.user.role == 1:
                posts2 = top_posts(10)
                comments = top_comments(10)
                upload_url = blobstore.create_upload_url('/blog/upload/')
                views = popular_posts()
                self.render("blog_newpost.html", loadblog = True, recentposts = posts2, recentcomments = comments, viewcount = get_view_count('-1'), uploadurl = upload_url, popularposts = views)
            else:
                self.redirect("/blog")
        else:
            self.redirect("/login")
 
def add_photo_img(url, path):
    end = url.find('/', 7)
    return '<img class="galleryImg" src="' + url[0:end] + path + '"><br />'

class MediaUpload(BlogHandler, blobstore_handlers.BlobstoreUploadHandler):
    def post(self, post_id = None):
        if not self.user:
            self.redirect('/blog')

        subject = self.request.get('subject')
        content = quopri.decodestring(self.request.get('content'))
        category = int(self.request.get('category'))
        upload_files = self.get_uploads('file')

        if not category:
            category = Categories.uncategorized

        if subject and content:
            if upload_files:
                blob_info = upload_files[0]
                content = add_photo_img(self.request.url, '/media/%s' % blob_info.key()) + content
            category_old = None
            if post_id:
                post = single_post(post_id)
                category_old = post.category
                Post.update(post_id, subject, content, category)
            else:
                post = Post.save(subject, content, category)
            
            single_post(post.key().id(), True)
            top_posts(10, True)
            if category_old and category != post.category:
                posts_by_category(category_old, True)
            posts_by_category(category, True)
            self.redirect('/blog/%s' % str(post.key().id()))
        else:
            posts2 = top_posts()
            error = "subject and/or content, please!"
            self.render("blog_newpost.html", loadblog = True, subject=subject, content=content, category=category, error=error, )

class ServeHandler(BlogHandler, blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, resource):
      resource = str(urllib.unquote(resource))
      blob_info = blobstore.BlobInfo.get(resource)
      self.send_blob(blob_info)
    
class CodingPosts(BlogHandler):
    def get(self):
        posts = posts_by_category(Categories.coding)
        posts2 = top_posts()
        comments = top_comments()
        views = popular_posts()
        self.render('blog.html', loadblog = True, posts = posts, loadcoding = True, recentposts = posts2, recentcomments = comments, viewcount = get_view_count('-1'), popularposts = views)
class DesignPosts(BlogHandler):
    def get(self):
        posts = posts_by_category(Categories.design)
        posts2 = top_posts()
        comments = top_comments()
        views = popular_posts()
        self.render('blog.html', loadblog = True, posts = posts, loaddesign = True, recentposts = posts2, recentcomments = comments, viewcount = get_view_count('-1'), popularposts = views)
class PhotographyPosts(BlogHandler):
    def get(self):
        posts = posts_by_category(Categories.photography)
        posts2 = top_posts()
        comments = top_comments()
        views = popular_posts()
        self.render('blog.html', loadblog = True, posts = posts, loadphotography = True, recentposts = posts2, recentcomments = comments, viewcount = get_view_count('-1'), popularposts = views)
class VolunteerPosts(BlogHandler):
    def get(self):
        posts = posts_by_category(Categories.volunteer)
        posts2 = top_posts()
        comments = top_comments()
        views = popular_posts()
        self.render('blog.html', loadblog = True, posts = posts, loadvolunteer = True, recentposts = posts2, recentcomments = comments, viewcount = get_view_count('-1'), popularposts = views)
class StartupPosts(BlogHandler):
    def get(self):
        posts = posts_by_category(Categories.startup)
        posts2 = top_posts()
        comments = top_comments()
        views = popular_posts()
        self.render('blog.html', loadblog = True, posts = posts, loadstartup = True, recentposts = posts2, recentcomments = comments, viewcount = get_view_count('-1'), popularposts = views)
class UncategorizedPosts(BlogHandler):
    def get(self):
        posts = posts_by_category(Categories.uncategorized)
        posts2 = top_posts()
        comments = top_comments()
        views = popular_posts()
        self.render('blog.html', loadblog = True, posts = posts, loaduncategorized = True, recentposts = posts2, recentcomments = comments, viewcount = get_view_count('-1'), popularposts = views)

app = webapp2.WSGIApplication([('/?', BlogFront),
                                ('/blog/?', BlogFront),
                                ('/blog/nextpage/(\d+)/?', BlogFrontNext),
                                ('/blog/(\d+)/?', PostPage),
                                ('/blog/(\d+)/edit/?', EditPostPage),
                                ('/blog/newpost/?', NewPost),
                                ('/blog/upload/?', MediaUpload),
                                ('/blog/upload/(\d+)/?', MediaUpload),
                                ('/blog/coding/?', CodingPosts),
                                ('/blog/design/?', DesignPosts),
                                ('/blog/photography/?', PhotographyPosts),
                                ('/blog/volunteer/?', VolunteerPosts),
                                ('/blog/startup/?', StartupPosts),
                                ('/blog/uncategorized/?', UncategorizedPosts)
                               ],
                              debug=True)

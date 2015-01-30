import random
import hashlib
import logging
import datetime
from string import letters
from google.appengine.ext import db
#from google.appengine.dist import use_library
#use_library('django', '1.3')
#from django.template.defaultfilters import slugify

##### User model
def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)

def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)

def users_key(group = 'default'):
    return db.Key.from_path('users', group)

class User(db.Model):
    name = db.StringProperty(required = True)
    pw_hash = db.StringProperty(required = True)
    email = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add = True)
    role = db.IntegerProperty()

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, parent = users_key())

    @classmethod
    def by_name(cls, name):
        u = User.all().filter('name =', name).ancestor(users_key()).get()
        return u

    @classmethod
    def register(cls, name, pw, email = None, role = None):
        pw_hash = make_pw_hash(name, pw)
        return User(parent = users_key(),
                    name = name,
                    pw_hash = pw_hash,
                    email = email,
                    role = role)

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u

##### blog post - Post model
def posts_key(group = 'default'):
    return db.Key.from_path('posts', group)

class Categories():
    uncategorized = 0
    coding = 1
    design = 2
    photography = 3
    volunteer = 4
    startup = 5

class Post(db.Model):
    subject = db.StringProperty(required = True)
    subject_slug = db.StringProperty(required = False)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)
    comment_count = db.IntegerProperty()
    category = db.IntegerProperty(indexed = True)
        
    @classmethod
    def by_id(cls, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=posts_key())
        return db.get(key)
        
    @classmethod
    def by_created(cls, limit):
        posts = Post.all().order('-created').run(limit = limit)
        return list(posts)

    @classmethod
    def by_category(cls, category):
        posts = Post.all().filter('category = ', category).order('-created').run()
        return list(posts)

    @classmethod
    def get_total_count(cls):
        return Post.all().count()

    @classmethod
    def save(cls, subject, content, category):
        #subject_slug = slugify(subject)
        p = Post(parent = posts_key(), subject = subject, content = content, category = category)
        p.comment_count = 0
        p.put()
        return p

    @classmethod
    def update_comment_count(cls, post_id, comment_count):
        p = Post.by_id(int(post_id))
        p.comment_count = comment_count
        p.put()
        return p

    @classmethod
    def update(cls, post_id, subject, content, category):
        p = Post.by_id(int(post_id))
        p.subject = subject
        p.content = content
        p.category = category
        #p.subject_slug = slugify(subject)
        if not p.comment_count:
            p.comment_count = 0
        p.put()
        return p

##### blog comment - Comment model
def comments_key(group = 'default'):
    return db.Key.from_path('comments', group)

class Comment(db.Model):
    post_id = db.IntegerProperty(required = True, indexed = True)
    post_subject = db.StringProperty()
    post_subject_slug = db.StringProperty()
    username = db.StringProperty(required = True)
    email = db.StringProperty()
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    
    @classmethod
    def by_post(cls, post_id):
        comments = Comment.all().filter('post_id = ', int(post_id)).order('created').ancestor(comments_key()).run()
        return list(comments)

    @classmethod
    def by_created(cls, limit):
        comments = Comment.all().order('-created').ancestor(comments_key()).run(limit=limit)
        return list(comments)
    
    @classmethod
    def delete_all_with_empty_content(cls):
        comments = Comment.all().ancestor(comments_key()).run()
        for comment in comments:
            if len(comment.content.strip()) == 0: #or comment.created > datetime.datetime(2014,1,1):
                post_id = comment.post_id
                logging.info('deleting comment from %s in %s', comment.username, comment.post_subject)
                db.delete(comment)
                post = Post.by_id(post_id)
                post.update_comment_count(post_id, post.comment_count-1)
        return

    @classmethod
    def save(cls, post_id, username, content, email):
        p = Post.by_id(int(post_id))
        subject = ""
        subject_slug = ""
        if p:
            subject = p.subject
            #subject_slug = slugify(subject)
        if content and len(content.strip()) != 0:
            c = Comment(parent=comments_key(), post_id = int(post_id), post_subject = subject, username = username, content = content, email = email, post_subject_slug = subject_slug)
            c.put()
            return c

##### page view count - View model
def views_key(group = 'siteadmin'):
    return db.Key.from_path('views', group)

class View(db.Model):
    post_id = db.IntegerProperty(required = True, indexed = True)
    post_subject = db.StringProperty()
    post_subject_slug = db.StringProperty()
    count = db.IntegerProperty(required = True)
    last_modified = db.DateTimeProperty(auto_now = True)
    
    @classmethod
    def by_post(cls, post_id):
        view = View.all().filter('post_id = ', int(post_id)).ancestor(views_key()).get()
        return view

    @classmethod
    def by_viewcount(cls, limit):
        views = View.all().order('-count').ancestor(views_key()).run(limit=limit)
        return list(views)

    @classmethod
    def increment_count(cls, post_id):
        if post_id != '-1':
            blogview = View.by_post('-1')
            if not blogview:
                blogview = View(parent = views_key(), post_id = -1, count = 0)
            blogview.count = blogview.count + 1
            blogview.put()
        v = View.by_post(post_id)
        if not v:
            v = View(parent = views_key(), post_id = int(post_id), count = 0)
        v.count = v.count + 1
        
        if not v.post_subject:
            p = Post.by_id(int(post_id))
            subject = ""
            subject_slug = ""
            if p:
                subject = p.subject
                #subject_slug = slugify(subject)
            v.post_subject = subject
            v.post_subject_slug = subject_slug
        v.put()
        return v
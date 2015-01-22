#coding:utf-8

import os
import time
import math
import torndb
import pymongo
import tornado.ioloop
import tornado.web
import tornado.httpserver  
from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)
define("mysql_host", default="127.0.0.1:3306", help="blog database host")
define("mysql_database", default="blog", help="blog database name")
define("mysql_user", default="root", help="blog database user")
define("mysql_password", default="zhy", help="blog database password")



#定义Application信息，它是继承tornado.web.Application 的
class Application(tornado.web.Application):
    def __init__(self):
    #这里就是url对应的控制器，下面分别对应一个类，来处理里面的逻辑
        handlers = [
            (r"/", MainHandler),
            (r"/add", AddHandler),
            (r"/add_blog/", AHandler),
            (r"/detail",DetailHandler),
            (r"/login",LoginHandler),
            (r'/logout', LogoutHandler),
            (r'/comment/(\d+)',CommentHandler),
            (r'/articles',ArticlesHandler),
        ]
		#设置，如博客标题，模板目录，静态文件目录，xsrf，是否调试
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            cookie_secret="bZJc2sWbQLKos6GkHn/VB9oXwQt8S0R0kRvJ5/xJ89E=",
            xsrf_cookies=True,
            login_url="/login",
            debug=True,
        )
		#然后调用tornado.web.Application类的__init__函数加载进来
        tornado.web.Application.__init__(self, handlers, **settings)

		# Have one global connection to the blog DB across all handlers
		#数据库连接信息
        self.db = torndb.Connection(
            host=options.mysql_host, database=options.mysql_database,
            user=options.mysql_user, password=options.mysql_password)


        mongo_conn = pymongo.Connection('localhost',27017)
        self.mongo_db = mongo_conn['blog_log']

class BaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		return self.get_secure_cookie("username")

class MainHandler(tornado.web.RequestHandler):
	def get(self):
		page = int(self.get_argument('page',1))
		counts = self.application.db.query('select count(*) as count from blog')
		pages = int(math.ceil(counts[0]['count']/10.0))
		page = page if pages>page else pages
		start_num,end_num= (page-1)*10,page*10
		self.application.mongo_db.access_log.insert({'uri':self.request.uri,'remote_ip':self.request.remote_ip,'time':int(time.time())})
		articles = self.application.db.query('select * from blog limit %s,%s',start_num,end_num)
		kinds = self.application.db.query('select * from kind')
		for i in range(len(articles)):
			articles[i]['content'] = articles[i]['content'][:200]+'...'
			articles[i]['create_time'] = time.strftime("%Y-%m-%d", time.localtime(articles[i]['create_time']))
		self.render('index.html',articles = articles,kinds = kinds,page = page,pages = pages)

class ArticlesHandler(tornado.web.RequestHandler):
	def get(self):
		kinds = self.application.db.query('select * from kind')
		kind = self.get_argument('kind','')
		kind = [kind] if kind else [x['id'] for x in kinds]
		self.application.mongo_db.access_log.insert({'uri':self.request.uri,'remote_ip':self.request.remote_ip,'time':int(time.time())})
		articles = self.application.db.query('select * from blog where kind_id in %s limit 10',tuple(kind))
		for i in range(len(articles)):
			articles[i]['content'] = articles[i]['content'][:200]+'...'
			articles[i]['create_time'] = time.strftime("%Y-%m-%d", time.localtime(articles[i]['create_time']))
		self.render('index.html',articles = articles,kinds = kinds)


class AddHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render('add_blog.html')

class AHandler(tornado.web.RequestHandler):
	def post(self):
		title = self.get_argument('title','')
		author = self.get_argument('author','GaoJian')
		content = self.get_argument('content','')
		t = int(time.time())
		self.application.db.execute('insert into blog (title,author,content,create_time) values (%s,%s,%s,%s)',title,author,content,t)
		self.write('yes')

class DetailHandler(tornado.web.RequestHandler):
	def get(self):
		id = int(self.get_argument('id',-1))
		kinds = self.application.db.query('select * from kind')
		self.application.mongo_db.access_log.insert({'uri':self.request.uri,'remote_ip':self.request.remote_ip,'time':int(time.time())})
		articles = self.application.db.query('select * from blog where id = %s',id)
		if articles:
			article = articles[0]
			article['content'] = article['content']
			article['create_time'] = time.strftime("%Y-%m-%d", time.localtime(article['create_time']))
			self.application.db.execute('update blog set clicks = %s where id = %s',article['clicks']+1,id)
			comments = self.application.db.query('select * from comment where blog_id = %s',id)
			self.render('blog.html',article = article,comments = comments,kinds = kinds)
		else:
			self.write('something wrong')

class LoginHandler(BaseHandler):
	def get(self):
		self.render('login.html')
	def post(self):
		name = self.get_argument('username','')
		passwd = self.get_argument('passwd','')
		user = self.application.db.query('select is_super from user where name = %s and passwd = %s',name,passwd)
		if user and user[0]['is_super']:
			self.set_secure_cookie("username", self.get_argument("username"))
			self.redirect('/add')
		else:
			self.write('您没有权限')

class LogoutHandler(BaseHandler):
	def get(self):
		if (self.get_argument("logout", None)):
			print 'logout...'
		else:
			print 'logout fail'
		self.clear_cookie("username")
		self.redirect("/")

class CommentHandler(tornado.web.RequestHandler):
	def post(self,id):
		print 'id : ',id
		text = self.get_argument('comment','')
		t = int(time.time())
		self.application.db.execute('insert into comment (blog_id,text,create_time) values (%s,%s,%s)',id,text,t)
		self.redirect('/detail?id='+str(id))




if __name__ == "__main__":
	tornado.options.parse_command_line()  
	app = tornado.httpserver.HTTPServer(Application())  
	app.listen(options.port)  
	tornado.ioloop.IOLoop.instance().start()
# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

from bs4 import BeautifulSoup
import sqlite3 
import urllib2
import json
from urlparse import urljoin, urlparse
import codecs
import re
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(os.path.split(fdir)[0])[0]
sys.path.append(root)

class crawler(object):
    def __init__(self, dbname):
        # check the data directory
        self.dir_data = os.path.join(root,'data','cmt')
        if not os.path.exists(self.dir_data): # if dir does not exist
            print 'Error: Data directory {:s} does not exist.'.format(self.dir_data)
            exit()
        # connect database
        self.con = sqlite3.connect(dbname)
        self.con.execute('''
            create table if not exists Indexed_Links
            (url text)
            ''')
        self.con.execute('''
            create table if not exists SnowBall_Users
            (uid text, url text)
            ''')
        self.send_headers = {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) \
        AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.81 Safari/537.36', 
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Connection':'keep-alive',
        'Host':'xueqiu.com',
        'Cookie':r'xxxxxx'}        

    def __del__(self):
        self.con.close()

    def dbcommit(self):
        self.con.commit()
    
    def isindexed(self, url):
        """
        Return true if this url is already indexed
        """
        url = self.con.execute("select url from Indexed_Links \
            where url='{:s}'".format(url)).fetchone() 
        if url is None:
            return False
        else:
            return True
    
    def record_SnowBallUser(self, uid, url):
        """
        Record SnowBall user in database
        """
        self.con.execute("insert into SnowBall_Users \
            values ('{0:s}', '{1:s}')".format(uid, url))  
        self.dbcommit()       
    
    def mark_as_indexed(self, url):
        """
        Mark the uid/url as indexed
        """
        self.con.execute("insert into Indexed_Links \
            values ('{0:s}')".format(url))
        self.dbcommit() 
    
    def get_user_id(self, html):
        """
        Extract the SnowBall user id from an HTML page of SnowBall website
        """
        uid_pattern = re.compile("data-user-id='\w+'")
        uid_obj = uid_pattern.search(html)
        if uid_obj is None:
            return ''
        else:
            uid = html[uid_obj.start()+len("data-user-id='"):uid_obj.end()-1]
            return uid
    
    def get_raw_comments(self, html):
        """
        Extract comments from an HTML page of SnowBall website
        """
        # get start position of the comments
        pos_start = html.find('SNB.data.statuses = ') + len('SNB.data.statuses = ')
        # get end position of the comments
        end_pattern = re.compile('"maxPage":\d+}')
        end_str = end_pattern.search(html)
        if end_str is None:
            return ''
        else:
            pos_end = end_str.end()
        # get the part of HTML that contains comments    
        data = html[pos_start:pos_end]
        return data
    
    def write_raw_comments(self, cmtfile, uid, data):
        """
        Write raw comments into cmtfile
        """
        # convert these comment data into dict via json
        dic = json.loads(data)
        comments = dic['statuses']
        for i in range(len(comments)):
            cmtfile.write('"{0:s}", "{1:s}"'.format(uid, comments[i]['text']))
            cmtfile.write('\n')
        
    def dbcommit(self):
        self.con.commit()
    
    def parse_page(self, page):
        # check whether this page belongs to SnowBall website
        netloc = urlparse(page).netloc
        if netloc != r'xueqiu.com':
            return
        # try to open the page
        print 'Requesting ' + page 
        # mark this url as indexed
        self.mark_as_indexed(page) 
        try:
            req = urllib2.Request(page, headers=self.send_headers)
            resp = urllib2.urlopen(req, timeout=5)
        except:
            print "Could not open {:s}".format(page) 
            return
        # try to read the page
        try:
            html = resp.read()
        except:
            print "Could not read page {:s}".format(page) 
            return
        # try to parse the page
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            print "Could not parse page {:s}".format(page) 
            return
        # get useful links in this page
        for link in soup.find_all('a'):
            if 'href' in link.attrs.keys():
                url = urljoin(page, link['href'])
                if urlparse(url).netloc != r'xueqiu.com': continue
                url = url.split('#')[0]  # remove location portion
                if url[0:4]=='http' and not self.isindexed(url):
                    self.newpages.add(url)    
        # get SnowBall user id
        uid = self.get_user_id(html)   
        if uid == '':
            return     
        # get raw comments
        cmtdata = self.get_raw_comments(html) 
        if cmtdata == '':
            return
        print 'Data obtained from ' + page
        # record user id and url of the SnowBall user  
        self.record_SnowBallUser(uid, page)     
        # try to create a file and store comments
        fname = uid
        pathname = os.path.join(self.dir_data, fname) 
        try:                    
            cmtfile = codecs.open(pathname, 'wb', 'utf-8')
        except IOError:
            print 'Error: Could not store cmt data of ' + page
            return
        else:
            self.write_raw_comments(cmtfile, uid, cmtdata) 
            cmtfile.close()   
                
    def parse_pages(self):
        # to store new pages that to be crawl in next loop
        self.newpages = set()
        # start to parse pages at hand
        for page in self.pages:
            self.parse_page(page)
        # update pages
        self.pages = self.newpages 
    
    def crawl(self, init_pages, depth=3):
        self.pages = init_pages # init pages
        for i in range(depth):
            self.parse_pages()
            
            
if __name__ == '__main__':
    pages = [r'http://xueqiu.com/'] #[r'http://xueqiu.com/comy28']
    crawler = crawler('SnowBallUsers.db')
    crawler.crawl(pages)

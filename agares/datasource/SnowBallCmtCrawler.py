#! /usr/bin/python

import ipdb
from bs4 import BeautifulSoup
import sqlite3 
import urllib.request
from urllib.parse import urljoin, urlparse, urlunparse, quote
import json
import time
import math
from datetime import datetime, timedelta
import re
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(os.path.split(fdir)[0])[0]
import sys
sys.path.append(root)
from threading import Thread, Lock
from queue import Queue

class SnowBallCmtCrawler(object):
    """
    A crawler class that can download comment data ('cmt' for short ) from SnowBall website
    into 'data/SnowBall_cmt' folder. The data are preserved according to their created date.
    
    To load the downloaded SnowBall cmt data, use
        pd.read_csv(cmtfilename, sep='%_%', encoding="utf-8", engine='python'),
    where cmtfilename is the date of the cmt data that you would like to load plus '.csv'
    
    You can use the SnowBallCmtLoader class to load the downloaded data for you. Here is 
    an example:
        from agares.datasource.SnowBallCmtLoader import SnowBallCmtLoader
        SBLoader = SnowBallCmtLoader()
        df_cmt = SBLoader.load('2016-02-14')
        print(df_cmt) 
    """
    def __init__(self, dt_start, dt_end, init_pages, UseStoredURL = False, DropIsRecorded = False):
        """
        Args:
            dt_start(datetime.date): start date
            dt_end(datetime.date): the day after end date, i.e., the cmt data at this date will 
                                    not be downloaded.
            init_pages(str): list of urls that are used to start     
        """
        # check the data directory
        dir_data = os.path.join(root,'data','SnowBall_cmt')
        if not os.path.exists(dir_data): # if dir does not exist
            print('Error: Data directory {:s} does not exist.'.format(dir_data))
            exit()
        # check time scope setting
        assert dt_start < dt_end, "Time scope setting (dt_start, dt_end) is not correct"
        # set time scope
        self.dt_start, self.dt_end = dt_start, dt_end
        # initial cmtfiles 
        one_day = self.dt_start
        self.cmtfiles = {} # {date(str): file handler, }
        self.cmtfile_mutex = {} # {date(str): thread lock), } 
        while one_day < self.dt_end:
            date = str(one_day)            
            fname = date + '.csv'
            pathname = os.path.join(dir_data, fname) 
            if os.path.exists(pathname): 
                try:
                    self.cmtfiles[date] = open(pathname, 'a')
                except IOError:
                    print("IOError: Could not open cmtfile {:s}".format(pathname))
                    exit()
            else:
                try:
                    self.cmtfiles[date] = open(pathname, 'wt')
                    self.cmtfiles[date].write('%_%'.join(['PageUserID', 'CommentUserID', 'Datetime', 'RawComment']))
                    self.cmtfiles[date].write('\n')
                except IOError:
                    print("IOError: Could not create cmtfile {:s}".format(pathname))
                    exit()
            # create threading.Lock() for each cmtfile
            self.cmtfile_mutex[date] = Lock()
            one_day += timedelta(days=1)   
        # compute the path of the database     
        self.dbpathname = os.path.join(dir_data, 'SnowBallUsers.db')        
        # get modified date if database already exists
        dbdate = datetime.now().date()
        if os.path.exists(self.dbpathname):
            dbfile_mtime = time.ctime(os.path.getmtime(self.dbpathname))
            dbfile_mtime = datetime.strptime(dbfile_mtime, "%a %b %d %H:%M:%S %Y")
            dbdate = dbfile_mtime.date()    
        # connect database
        con = sqlite3.connect(self.dbpathname)
        # drop recorded data (Table Is_Recorded) if required
        if DropIsRecorded == True:
            self.drop_table_Is_Recorded(con)
        # create table of database
        con.execute('''
            create table if not exists Indexed_Links
            (url text)
            ''')        
        con.execute('''delete from Indexed_Links''')
        con.execute('''
            create table if not exists Is_Recorded
            (cmt_id text, user_id text)
            ''')
        con.execute('''
            create table if not exists SnowBallUsers
            (uid text, url text)
            ''')
        # define header
        self.send_headers = {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) \
        AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.81 Safari/537.36', 
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Connection':'keep-alive',
        'Host':'xueqiu.com',
        'Cookie':r'xxxxxx'}     
        # init pages
        self.pages = Queue()
        for page in init_pages:
            quote_page = self.check_and_quote_url(page)
            if quote_page is None: 
                print("Error: Bad initial page {:s}".format(page))
                print("Initial page should belong to xueqiu.com")
                exit()
            # mark this url as indexed
            self.mark_as_indexed(con, quote_page)
            self.pages.put(quote_page)
        # use stored urls as initial pages if database has not yet been modified today or 
        # is required (i.e., UseStoredURL is set to True)
        if dbdate < datetime.now().date() or UseStoredURL == True:
            # append stored PageUser urls as initial pages
            stored_urls = con.execute('''select * from SnowBallUsers''')
            for PageUser, url in stored_urls:
                quote_url = self.check_and_quote_url(url)
                if quote_url is None:
                    continue
                # mark this url as indexed
                self.mark_as_indexed(con, quote_url)            
                self.pages.put(url)
        # to store the number of PageUsers we have crawled in this run
        self.n_PageUser = 0
        # create a threading.Lock() for .n_PageUser
        self.n_PageUser_mutex = Lock()
        # prepare timescope for printing at the end
        self.Timescope = (str(dt_start), str(dt_end-timedelta(days=1)))      
        # close database
        con.close()
        # start timing 
        self.start_time = time.time()
        
    def __del__(self):
        # close all cmtfiles
        for date in self.cmtfiles.keys():
            self.cmtfiles[date].close()
        # print
        print("\nDone. New comments of {:d} PageUsers were recorded in this run.".format(self.n_PageUser))
        print("Timescope: from {0:s} to {1:s}".format(self.Timescope[0], self.Timescope[1]))

    def dbcommit(self, con):
        con.commit()

    def drop_table_Is_Recorded(self, con):
        """
        Drop the table Is_Recorded
        """
        con.execute('drop table Is_Recorded')
        print("Table Is_Recorded is droped")
        
    def is_indexed(self, con, url):
        """
        Return true if this url has been indexed
        """
        url = con.execute("select url from Indexed_Links \
            where url='{:s}'".format(url)).fetchone() 
        if url is None:
            return False
        else:
            return True
            
    def is_recorded(self, con, cmt_id, user_id):
        """
        Return true if this comment of the user has been recorded
        """
        cmt_id = con.execute("select cmt_id from Is_Recorded \
            where cmt_id='{0:d}' and user_id='{1:d}'".format(cmt_id, user_id)).fetchone() 
        if cmt_id is None:
            return False
        else:
            return True
    
    def record_SnowBallUser(self, con, PageUserID, url):
        """
        Record SnowBall user id and its page url into database
        """
        con.execute("insert into SnowBallUsers \
            values ('{0:s}', '{1:s}')".format(PageUserID, url))  
        self.dbcommit(con)       
    
    def mark_as_indexed(self, con, url):
        """
        Mark the url as indexed
        """
        con.execute("insert into Indexed_Links \
            values ('{:s}')".format(url))
        self.dbcommit(con) 
        
    def mark_as_recorded(self, con, cmt_id, user_id):
        """
        Mark the comment of the user as recorded
        """        
        con.execute("insert into Is_Recorded \
            values ('{0:d}', '{1:d}')".format(cmt_id, user_id))
        self.dbcommit(con) 
    
    def get_PageUserID(self, html):
        """
        Extract the SnowBall user id from an HTML page of the SnowBall website
        """
        PageUserID_obj = re.search("data-user-id='\w+'", html)
        if PageUserID_obj is None:
            return ''
        else:
            PageUserID = PageUserID_obj.group(0)[14:-1] # get the '\w+' part
            return PageUserID
    
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
    
    def to_datetime(self, SBdatetime):
        """
        Convert SnowBall webstie page datetime format into (datetime.date, '%H:%M').
        If SBdatetime is '' or None, return (None, '').
        """
        if SBdatetime == '' or SBdatetime == None:
            return None, ''
        if SBdatetime.find('今天') is not -1:
            hour_minute = re.search('\d{2}:\d{2}', SBdatetime).group() # search %H:%M
            return datetime.now().date(), hour_minute 
        if SBdatetime.find('分钟前') is not -1:
            minutebefore = re.search('\d+', SBdatetime).group() # search %M
            date_time = datetime.now() - timedelta(minutes=int(minutebefore))
            return date_time.date(), '{0:02d}:{1:02d}'.format(date_time.hour, date_time.minute)
        if SBdatetime.find('秒前') is not -1:
            secondbefore = re.search('\d+', SBdatetime).group() # search %S
            date_time = datetime.now() - timedelta(seconds=int(secondbefore))
            return date_time.date(), '{0:02d}:{1:02d}'.format(date_time.hour, date_time.minute)
        if re.search('\d{4}-\d{2}-\d{2}', SBdatetime) is None:
            SBdatetime = str(datetime.now().year) +'-'+ SBdatetime # convert to '%Y-%m-%d %H:%M'
        # convert to datetime
        SBdatetime = datetime.strptime(SBdatetime, '%Y-%m-%d %H:%M')
        return SBdatetime.date(), '{0:02d}:{1:02d}'.format(SBdatetime.hour, SBdatetime.minute) 
    
    def write_raw_comments(self, con, PageUserID, cmtdata, one_day):
        """
        Write raw comments into cmtfile of date:one_day
        """
        # convert these comment data into dict via json
        dic = json.loads(cmtdata)
        comments = dic['statuses']
        # to record whether we write a record this time
        do_record = False
        # check and process each comment
        for i in range(len(comments)):
            # get created time of the comment
            SBdatetime = comments[i]['timeBefore']
            SBdate, hour_minute = self.to_datetime(SBdatetime)     
            # process the comments whose created date is equal to one_day  
            if one_day == SBdate: 
                date = str(one_day)
                comment_ID = comments[i]['id']
                comment_userID = comments[i]['user_id']
                if not self.is_recorded(con, comment_ID, comment_userID):
                    raw_comment = comments[i]['text']
                    with self.cmtfile_mutex[date]:
                        self.cmtfiles[date].write('{0:s}%_%{1:s}%_%{2:s}%_%{3:s}'.format(PageUserID, \
                                                    str(comment_userID), hour_minute, raw_comment))
                        self.cmtfiles[date].write('\n')
                    self.mark_as_recorded(con, comment_ID, comment_userID)
                    do_record = True
        return do_record
    
    def check_and_quote_url(self, url):
        """
        check url and quote it to avoid Chinese character errors
        return None if the page is inappropriate; otherwise return a quote page.
        """
        if url == 'http://xueqiu.com/':
            return url
        obj = urlparse(url)
        scheme, netloc, path = obj.scheme, obj.netloc, obj.path
        # check the scheme of url
        if scheme != 'http':
            return None
        # check whether this page belongs to SnowBall website
        if netloc != 'xueqiu.com':
            return None
        # check path
        if len(path) <= 1 or len(path) >= 40:
            return None
        if path.endswith('＃'):
            path = path[:-1]
        if path.endswith('/report'):
            path = path[:-7]
        if path.startswith('/P/') or path.startswith('/p/'):
            return None
        if path.startswith('/n/GT%25'):
            return None
        if path.startswith('/about/'):
            return None
        if path.startswith('/account/'):
            return None
        if path.startswith('/calendar/'):
            return None
        if path.startswith('/n/') and path.find('%2525')>0:
            return None  
        if path.find('http:/')>0:
            return None        
        # quote the url (avoid Chinese character errors)
        quote_path = quote(path)
        quote_url = urlunparse((scheme, netloc, quote_path, '', '', ''))
        return quote_url
    
    def parse_page(self, con, page): 
        """
        Parse one page
        """
        # request page 
        try:
            req = urllib.request.Request(page, headers=self.send_headers)
            resp = urllib.request.urlopen(req, timeout=10)
        except:
            print("Could not open {:s}".format(page)) 
            return
        # try to read the page
        try:
            html = resp.read().decode('UTF-8')
        except:
            print("Could not read page {:s}".format(page)) 
            return
        # try to parse the page
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            print("Could not parse page {:s}".format(page)) 
            return
        # get useful links in this page
        for link in soup.find_all('a'):
            if 'href' in link.attrs.keys():
                url = urljoin(page, link['href'])
                quote_url = self.check_and_quote_url(url)   
                if quote_url is None:
                    continue
                if not self.is_indexed(con, quote_url):
                    self.pages.put(quote_url)
                    # mark this url as indexed
                    self.mark_as_indexed(con, quote_url)
        # get SnowBall user id of the page
        PageUserID = self.get_PageUserID(html)   
        if PageUserID == '':
            return     
        # get raw comments
        cmtdata = self.get_raw_comments(html) 
        if cmtdata == '':
            return
        #print('Data obtained from ' + page)
        # create one file for each date and store comments
        one_day = self.dt_start
        do_record = False
        while one_day < self.dt_end:            
            if self.write_raw_comments(con, PageUserID, cmtdata, one_day):
                do_record = True
            one_day += timedelta(days=1)
        # count how many PageUser we have crawl in this run
        if do_record is True: 
            # record page user id and page url of the SnowBall user  
            self.record_SnowBallUser(con, PageUserID, page)  
            # update n_PageUser
            with self.n_PageUser_mutex:  
                self.n_PageUser += 1
                # print
                cost_time = time.time() - self.start_time
                print('{0:d} PageUsers reached. Cost {1:.2f} sec.'.format(self.n_PageUser, \
                        cost_time))                
     
    def parse_page_thread(self):
        """
        Parse pages at hand
        """
        # connect database
        con = sqlite3.connect(self.dbpathname)
        while self.n_PageUser < self.max_PageUser: 
            page = self.pages.get(timeout = 60)
            if page == None:
                return        
            # parse page
            self.parse_page(con, page)  
        # close database
        con.close() 
        
    def assign_jobs(self):
        """
        Assign jobs to multiple threads
        """
        # maximum number of threads
        MaxThread = 16
        # to store threads
        t = {} # {int: Thread, }
        # Create and launch threads
        for i in range(MaxThread):
            t[i] = Thread(target=self.parse_page_thread)
            t[i].start()      
        # wait until all threads finish
        for i in t.keys():
            t[i].join()
    
    def crawl(self, max_PageUser):
        self.max_PageUser = max_PageUser
        # start crawling
        self.assign_jobs()
            
            
if __name__ == '__main__':
    init_pages = ['http://xueqiu.com/hq', 'http://xueqiu.com/', 'http://xueqiu.com/g/2257796463', \
                    'http://xueqiu.com/g/8389168261', 'http://xueqiu.com/g/1131705413']
    # set start and end date (end date is not included)
    dt_start, dt_end = datetime.now().date()-timedelta(days=2), datetime.now().date()+timedelta(days=1)     
    crawler = SnowBallCmtCrawler(dt_start, dt_end, init_pages)
    crawler.crawl(max_PageUser=4000)

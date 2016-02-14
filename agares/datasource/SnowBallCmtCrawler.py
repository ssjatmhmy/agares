import ipdb
from bs4 import BeautifulSoup
import sqlite3 
import urllib.request
import json
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
import codecs
import re
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(os.path.split(fdir)[0])[0]
import sys
sys.path.append(root)

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
    def __init__(self, dbname):
        # check the data directory
        self.dir_data = os.path.join(root,'data','SnowBall_cmt')
        if not os.path.exists(self.dir_data): # if dir does not exist
            print('Error: Data directory {:s} does not exist.'.format(self.dir_data))
            exit()
        # connect database
        dbpathname = os.path.join(self.dir_data, dbname)
        self.con = sqlite3.connect(dbpathname)
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
    
    def record_SnowBallUser(self, PageUserID, url):
        """
        Record SnowBall user id and its page url into database
        """
        self.con.execute("insert into SnowBall_Users \
            values ('{0:s}', '{1:s}')".format(PageUserID, url))  
        self.dbcommit()       
    
    def mark_as_indexed(self, url):
        """
        Mark the url as indexed
        """
        self.con.execute("insert into Indexed_Links \
            values ('{0:s}')".format(url))
        self.dbcommit() 
    
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
    
    def write_raw_comments(self, cmtfile, PageUserID, cmtdata, one_day):
        """
        Write raw comments into cmtfile
        """
        # convert these comment data into dict via json
        dic = json.loads(cmtdata)
        comments = dic['statuses']
        for i in range(len(comments)):
            # get created time of the comment
            SBdatetime = comments[i]['timeBefore']
            date, hour_minute = self.to_datetime(SBdatetime)   
            # SnowBall comment data were written over a period of time. We can pass the comments
            # whose created date is after one_day      
            if one_day < date:
                continue
            # if one_day > date, we have processed all the cases that one_day==date. So return.
            if one_day > date:
                return      
            # process the comments whose created date is equal to one_day          
            comment_userID = comments[i]['user_id']
            raw_comment = comments[i]['text']
            cmtfile.write('{0:s} %_% {1:s} %_% {2:s} %_% {3:s}'.format(PageUserID, str(comment_userID), hour_minute, raw_comment))
            cmtfile.write('\n')
        
    def dbcommit(self):
        self.con.commit()
    
    def parse_page(self, page):
        # check whether this page belongs to SnowBall website
        netloc = urlparse(page).netloc
        if netloc != r'xueqiu.com':
            return
        # try to open the page
        print('Requesting ' + page) 
        # mark this url as indexed
        self.mark_as_indexed(page) 
        try:
            req = urllib.request.Request(page, headers=self.send_headers)
            resp = urllib.request.urlopen(req, timeout=5)
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
                if urlparse(url).netloc != r'xueqiu.com': continue
                url = url.split('#')[0]  # remove location portion
                if url[0:4]=='http' and not self.isindexed(url):
                    self.newpages.add(url)    
        # get SnowBall user id of the page
        PageUserID = self.get_PageUserID(html)   
        if PageUserID == '':
            return     
        # get raw comments
        cmtdata = self.get_raw_comments(html) 
        if cmtdata == '':
            return
        print('Data obtained from ' + page)
        # record page user id and page url of the SnowBall user  
        self.record_SnowBallUser(PageUserID, page)
        # create one file for each date and store comments
        one_day = self.dt_start
        while one_day < self.dt_end:            
            fname = str(one_day) + '.csv'
            pathname = os.path.join(self.dir_data, fname) 
            #with codecs.open(pathname, 'wb', 'utf-8') as cmtfile:
            with open(pathname, 'a') as cmtfile:
                self.write_raw_comments(cmtfile, PageUserID, cmtdata, one_day)
            one_day += timedelta(days=1)

                
    def parse_pages(self):
        # to store new pages that to be crawl in next loop
        self.newpages = set()
        # start to parse pages at hand
        for page in self.pages:
            self.parse_page(page)
        # update pages
        self.pages = self.newpages 
    
    def crawl(self, dt_start, dt_end, init_pages, depth=2):
        # init pages
        self.pages = init_pages 
        # check time scope setting
        assert dt_start < dt_end, "Time scope setting (dt_start, dt_end) is not correct"
        # set time scope
        self.dt_start, self.dt_end = dt_start, dt_end
        # initial cmtfiles with indexes
        one_day = self.dt_start
        while one_day < self.dt_end:            
            fname = str(one_day) + '.csv'
            pathname = os.path.join(self.dir_data, fname) 
            with open(pathname, 'wt') as cmtfile:
                cmtfile.write('PageUserID %_% CommentUserID %_% Datetime %_% RawComment\n')
            one_day += timedelta(days=1)
        # start crawling
        for i in range(depth):
            self.parse_pages()
            
            
if __name__ == '__main__':
    init_pages = [r'http://xueqiu.com/', r'http://xueqiu.com/comy28', r'http://xueqiu.com/6049709616']
    crawler = SnowBallCmtCrawler('SnowBallUsers.db')
    # set start and end datetime
    dt_start, dt_end = datetime.now().date()-timedelta(days=1), datetime.now().date()+timedelta(days=1) 
    crawler.crawl(dt_start, dt_end, init_pages, depth=3)
    
    
    

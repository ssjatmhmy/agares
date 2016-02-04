import tushare as ts
import pandas as pd
import time
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(os.path.split(fdir)[0])[0]
import sys
sys.path.append(root)
from agares.datastruct import parse_cst_filename
from datetime import datetime, timedelta, date


class cst_loader(object):
    """
    Call tushare API to download stock candlestick data
    """
    def __init__(self):
        """
        Args:
            
        """
        self.ktypes = {"5Minute": '5', "15Minute": '15', "30Minute": '30', 
        "60Minute": '60', "1Day": 'D', "1Week": 'W', "1Month": 'M'}
        self.dir_data = os.path.join(root,'data')
        self.stock_basics = ts.get_stock_basics()
        
    def load(self, pstocks):
        """
        Download cst data and save them in .csv file (in /data)
        
        Args:
            pstocks(str): filename of cst data
        """
        DataReleasedTime = datetime.strptime("15:10:00", "%H:%M:%S").time()
        # compute the last date of cst data
        if datetime.now().time() >= DataReleasedTime:
            end = datetime.now().date() + timedelta(days = 1)
        else:
            end = datetime.now().date()
        # download cst data for all required pstocks 
        for pstock in pstocks:
	        # get info from filename 
	        # .ID(class StockID), .period(str)
            ID, period = parse_cst_filename(pstock)
            # get cst data file path
            fname = pstock + ".csv"      
            pathname = os.path.join(self.dir_data, fname)                  
            if os.path.exists(pathname): # if cst data file exists
                # get modified date and time
                file_mtime = time.ctime(os.path.getmtime(pathname))
                file_mtime = datetime.strptime(file_mtime, "%a %b %d %H:%M:%S %Y")
                if file_mtime.time() >= DataReleasedTime:
                    start = file_mtime.date() + timedelta(days = 1)
                else:
                    start = file_mtime.date()
                # make the cst data file up-to-date
                if start < end:
                    # download using tushare
                    df = self.download(ID.code, str(start), str(end), period)
                    if df is not None: # not empty
                        # update cst data file
                        df.to_csv(pathname, mode='a', header = None)
            else: # if cst data file not exists, download data and create it.
                # get listing date of the stock
                ListingDate = self.stock_basics.ix[ID.code]['timeToMarket']
                ListingDate = datetime.strptime(str(ListingDate), '%Y%m%d').date()
                # download using tushare
                df = self.download(ID.code, str(ListingDate), str(end), period)
                # save         
                df.to_csv(pathname)

    def download(self, code, start, end, period):
        """
        Download using tushare
        
        Returns:
            df: pd.DataFrame(datetime, open, close, high, low, [turnover], ...)
        """
        IsIndex, name = self.is_index(code)
        if period == '1Day':
            df = ts.get_h_data(code, start, end, index = IsIndex) 
            if df is not None:
                # reverse
                df = df.iloc[::-1]         
        else:
            df = ts.get_hist_data(name, start, end, ktype = self.ktypes[period])  
            if df is not None:
                # select what we need
                df = df.loc[:, ['open', 'close', 'high', 'low', 'turnover']]
                # reverse
                df = df.iloc[::-1]
        return df

    def is_index(self, code):
        """
        check whether the code is an index code that tushare knows.
        """
        indexes = {'000001': 'sh', '399001': 'sz', '000300': 'hs300', \
                    '000016': 'sz50', '399005': 'zxb', '399006': 'zxb'}
        if code in indexes:
            return True, indexes[code]
        else:
            return False, code


if __name__ == '__main__':
    pstocks = ['000001.sz-1Day', '000049.dsdc-1Day', '000518.shsw-1Day', '000544.zyhb-1Day', \
                '600004.byjc-1Day', '600038.zzgf-1Day', '600054.hsly-1Day', '600256.ghny-1Day', \
                '600373.zwcm-1Day', '600867.thdb-1Day', '600085.trt-1Day']
    cl = cst_loader()
    cl.load(pstocks)
         

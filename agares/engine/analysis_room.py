import ipdb
import os
import sys
import numpy as np
import pandas as pd
import math
from datetime import datetime
from agares.errors import FileDoesNotExist
from agares.datastruct import PStock, StockID, parse_cst_filename
import matplotlib.pyplot as plt


class AnalysisRoom(object):
    """
    Analysis room of an analysis.
    One analysis room can only load one analysis, and the period \
    candlestick data should all belong to one specific stock. 
    """
    def __init__(self, pstocks, dt_start, dt_end, n_ahead):
        self._analysis = None 
        # actual timescope of the back test, depending on the user setting and the available data 
        self.timescope = None
        # number of extra daily data for computation (ahead of start datatime)
        # set in the main program
        self.n_ahead = n_ahead
        # check whether datetime is proper
        assert(dt_start < dt_end)
        # is_Day_cst: to check whether there is at least one daily candlestick data in pstocks
        is_Day_cst_exist = False
        # load candlestick(cst) data
        # .stocks = {code(str): PStock,}
        self.stocks = {}
        for pstock in pstocks:
            # get info from filename
            # .ID(class StockID), .period(str)
            ID, period = parse_cst_filename(pstock) 
            if period == '1Day':
                is_Day_cst_exist = True
            if ID.code not in self.stocks:
                self.stocks[ID.code] = PStock(pstock, dt_start, dt_end, n_ahead)
            else:
                self.stocks[ID.code].load_cst(pstock, dt_start, dt_end, n_ahead)
        # remind user
        assert is_Day_cst_exist, "At least one item in pstocks should be daily candlestick data"
        # for convenience, store sz cst information as class PStock
        self.sz = PStock('000001.sz-1Day', dt_start, dt_end, n_ahead)
        # for convenience, store dayily close price of sz
        self.sz_daily_close = self.sz.cst['1Day']['close'].values[n_ahead:]
        # get sz daily time axis
        self.szTimeAxis = self.sz.cst['1Day'].index[n_ahead:] # pd.DataFrame.index
        # find missing daily candlestick data and fill them up in .stocks[code].missing_cst['1Day'] 
        # as pd.DataFrame 
        self.fill_missing_cst()
        # read candlestick data timescope from sz
        self.timescope = str(self.szTimeAxis[0]), str(self.szTimeAxis[-1]) 


    def fill_missing_cst(self):
        """ 
        Find missing daily candlestick data and fill them up 
        in .stocks[code].missing_cst['1Day'] as pd.DataFrame 
        """
        for code in self.stocks.keys():
            # get pd.DataFrame.columns of cst data
            columns = self.stocks[code].cst['1Day'].columns
            # tmp_cst, tmp_tickers: to store missing daily candlestick data
            tmp_cst = {column: [] for column in columns}
            tmp_tickers = []
            # clear ivar: last_normal_cst at the beginning of each loop
            last_normal_cst = None
            # start to search missing cst data
            atbegin_flag = True
            for ticker in self.szTimeAxis:
                if atbegin_flag: # if missing cst data at the beginning, fill up with zeros
                    try:
                        last_normal_cst = self.stocks[code].cst['1Day'].ix[ticker]
                    except KeyError:
                        tmp_tickers.append(ticker)
                        for column in columns:
                            tmp_cst[column].append(0.0)
                    else:
                        atbegin_flag = False
                else:
                    try:
                        last_normal_cst = self.stocks[code].cst['1Day'].ix[ticker]
                    except KeyError:
                        tmp_tickers.append(ticker)
                        for column in columns:
                            tmp_cst[column].append(last_normal_cst[column])
                    else:
                        pass
            # store missing cst as pd.DataFrame 
            self.stocks[code].missing_cst['1Day'] = pd.DataFrame(tmp_cst, index = tmp_tickers)


    def add_analysis(self, analysis):
        """
        Add the analysis and set the settings
        """
        self._analysis = analysis
	    
    def run(self):
        print('Running analysis..')
        self._analysis.perform_analysis(self.stocks, self.szTimeAxis, self.n_ahead)






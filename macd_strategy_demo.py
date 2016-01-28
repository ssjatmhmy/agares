# @file macd_strategy_demo.py
# @brief standard MACD strategy demo

import ipdb
from datetime import datetime
from agares.engine.ag import (
	Strategy,
	create_trading_system,
	run,
	buy,
	sell,
	report)
from talib import (MA, EMA)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

class MACD_Strategy(Strategy):
    """ 
    The standard MACD strategy on daily candlestick data.
    Buy an asset when dif rises above dea,
    and sell it vice versa.
    """
    def __init__(self, name, nslow, nfast, m):
	super(MACD_Strategy, self).__init__(name)
	self.nfast = nfast
	self.nslow = nslow
	self.m = m

    @staticmethod
    def MACD(price, nslow, nfast, m):
	emas = EMA(price, nslow)
	emaf = EMA(price, nfast)
	dif = emaf - emas
	dea = EMA(dif, m)
	macd = dif - dea
	return dif, dea, macd


    def compute_trading_points(self, cst, actual_ahead):
	"""
	Args:
            cst(pd.DataFrame): The variable name 'cst' is short for 'candlestick'
            actual_ahead(int): Number of extra daily data. We add extra daily data 
                        (before start date) for computing indexes such as MA, MACD. 
			These may help to avoid nan at the beginning of indexes.
			It can be set at the main program (var: n_ahead). However, 
			it would be smaller than you set because of lack of data.
			That's why we use a different variable name from that of main
			program.
	"""
	df_1day = cst['1Day']
	datetime_1day = df_1day.index
	close_1day = df_1day['close'].values

	# MACD
	dif, dea, _ = self.MACD(close_1day, self.nslow, self.nfast, self.m)
	df_macd = pd.DataFrame({'dif': dif, 'dea': dea}, 
				index = datetime_1day)

	# skip extra data
	df_macd = df_macd.iloc[actual_ahead:]
	close_1day = close_1day[actual_ahead:]

	#df_macd.plot()
	#plt.show()
	start_flag = 0
	hold_flag = 0
	for i, ticker in enumerate(df_macd.index):
	    # skip null value at the beginning
	    if np.isnan(df_macd.iloc[i]['dif']) or np.isnan(df_macd.iloc[i]['dea']):
		continue 
	    # skip the days of 'dif'>='dea' at the beginning
	    # those should be the days waiting fo selling, not buying, thus not suitable for a start
	    if (start_flag == 0) and (df_macd.iloc[i]['dif'] >= df_macd.iloc[i]['dea']):
		continue
	    else:
		start_flag = 1
	    # start trading
	    if (start_flag == 1):
		price = float(close_1day[i])
		if (hold_flag == 0) and (df_macd.iloc[i]['dif'] > df_macd.iloc[i]['dea']): 
		    # quantity is the number of shares (unit: boardlot) you buy this time 
		    quantity = buy(price, str(ticker), ratio = 1) 
		    hold_flag = 1
		if (hold_flag == 1) and (df_macd.iloc[i]['dif'] < df_macd.iloc[i]['dea']): 
		    # sell all the shares bought last time
		    sell(price, str(ticker), quantity) 
		    hold_flag = 0
	


if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of the interested stock
    # 'mp' refers to 'multiple period'
    mpstock = ['000001.sz-1Day']
    # create a trading strategy
    strategy = MACD_Strategy('Standard MACD strategy no.1', 26, 12, 9)
    # set start and end datetime
    dt_start, dt_end = datetime(1997,1,1), datetime(2016,1,27)
    # number of extra daily data for computation (ahead of start datatime)
    n_ahead = 80
    # settings of a trading system
    # capital:        Initial money for investment
    # StampTaxRate:   Usually 0.001. Only charge when sell.
    #                 The program do not consider the fact that buying funds do not charge this tax.  
    #                 So set it to 0 if the 'mpstock' is a fund.
    # CommissionChargeRate:   Usually 2.5e-4. The fact that commission charge is at least 5 yuan has
    #                         been considered in the program.
    settings = {'capital': 1000000, 'StampTaxRate': 0.00, 'CommissionChargeRate': 2.5e-4}
    # create a trading system
    create_trading_system(strategy, mpstock, dt_start, dt_end, n_ahead, settings)
    # start back testing
    run()
    # report performance of the trading system
    report(ReturnEquity = False)


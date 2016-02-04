# @file macd_strategy_demo.py
# @brief standard MACD strategy demo

import ipdb
from datetime import datetime
from talib import (MA, EMA)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(fdir)[0]
import sys
sys.path.append(root)
from agares.engine.ag import (
	Strategy,
	buy,
	sell,
	ask_agares)


class MACD_Strategy(Strategy):
    """ 
    A MACD strategy with risk control and position management (PM) on daily candlestick data.
    state 0: Prepare to buy some asset with a proportion of your cash. This proportion is called
	     first position.
    state 1: Buy an asset with first position when dif rises above dea. If the loss of this part 
	     of money reach certain ratio, sell it; otherwise wait until you have a small amount 
	     of floating profits. Then enter state 2.
    state 2: Sell all when you lose all your floating profits or dea falls under dif.
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


    def compute_trading_points(self, stocks, szTimeAxis, n_ahead):
	assert len(stocks) == 1, "This strategy allows only a daily candlestick data of one stock."
        code = stocks.keys().pop()
	cst = stocks[code].cst # get candlestick data
	DataTimeAxis = cst['1Day'].index

	# MACD
	dif, dea, _ = self.MACD(cst['1Day']['close'].values, self.nslow, self.nfast, self.m)

	# skip extra data
	TimeAxis = DataTimeAxis[n_ahead:]
	df_macd = pd.DataFrame({'dif': dif[n_ahead:], 'dea': dea[n_ahead:]}, 
				index = TimeAxis)

	#df_macd.plot()
	#plt.show()

	# set position management and Risk control parameters
	# the proportion of your current cash for the first investment (if you earn
	# some profits, you would invest the rest of the cash).
	first_position = 0.2
	# stop_loss: stop out when your loss of 1th position reach this proportion 
	stop_loss = 0.04
	# lock_profit: if your floating earn of 1th position reach this proportion,
	#              enter state 2: sell all at a proper time that before you 
	#              lose the profits.
	lock_profit = 0.05

	# start
	start_flag = 0
	state_flag = 0
	for ticker in TimeAxis:
	    # skip null value at the beginning
	    if np.isnan(df_macd.at[ticker, 'dif']) or np.isnan(df_macd.at[ticker, 'dea']):
		continue 
	    # skip the days of 'dif'>='dea' at the beginning
	    # those should be the days waiting fo selling, not buying, thus not suitable for a start
	    if (start_flag == 0) and (df_macd.at[ticker, 'dif'] >= df_macd.at[ticker, 'dea']):
		continue
	    else:
		start_flag = 1
	    # start trading
	    if (start_flag == 1):
		price = cst['1Day'].at[ticker,'close']
		if (state_flag == 0) and (df_macd.at[ticker, 'dif'] > df_macd.at[ticker, 'dea']): 
		    # quantity is the number of shares (unit: boardlot) you buy this time 
		    quantity1 = buy(code, price, str(ticker), ratio = first_position) # record quantity1
		    price1 = price # record the first buying price
		    state_flag = 1
		if state_flag ==1:
		    floating_earn_rate = (price - price1)/price1
		    if floating_earn_rate <= -stop_loss:
		        # stop out
		        sell(code, price, str(ticker), quantity1)
		        state_flag = 0
		    elif floating_earn_rate >= lock_profit:
			# enter state 2: lock in profits
			quantity2 = buy(code, price, str(ticker), ratio = 1) # record quantity2
			price2 = first_position * price1 + (1-first_position) * price
			state_flag = 2
		    else: # just wait
			pass
		if state_flag == 2:
		    if (price < price2) or (df_macd.at[ticker, 'dif'] < df_macd.at[ticker, 'dea']): 
		        # sell all the shares bought last time
		        sell(code, price, str(ticker), quantity1 + quantity2) 
		        state_flag = 0
	


if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create a trading strategy
    strategy = MACD_Strategy('A MACD strategy with risk control and position management', 26, 12, 9)
    # set start and end datetime
    dt_start, dt_end = datetime(1997,1,1), datetime(2016,1,26)
    # number of extra daily data for computation (ahead of start datatime)
    n_ahead = 80
    # capital:        Initial money for investment
    capital = 100000000
    # StampTaxRate:   Usually 0.001. Only charge when sell.
    #                 The program do not consider the fact that buying funds do not charge this tax.  
    #                 So set it to 0 if the 'pstocks' are ETF funds.
    StampTaxRate = 0.001
    # CommissionChargeRate:   Usually 2.5e-4. The fact that commission charge is at least 5 yuan has
    #                         been considered in the program.
    CommissionChargeRate = 2.5e-4
    # set to True if you would like to see the Plot of net value after the back-testing
    PlotNetValue = True

    settings = {'pstocks': pstocks, 'strategy': strategy, 'dt_start': dt_start, 'dt_end': dt_end,
    		'n_ahead': n_ahead, 'capital': capital, 'StampTaxRate': StampTaxRate, 
		'CommissionChargeRate': CommissionChargeRate, 'PlotNetValue': PlotNetValue}
    ask_agares(settings)


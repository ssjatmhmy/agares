# @file tree_planting_strategy.py
# @brief tree planting strategy

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


class TreePlantingStrategy(Strategy):
    """ 
    The Tree Planting strategy on daily candlestick data.
    Use standard MACD as trading signals, i.e., buy an asset when dif rises above dea,
    and sell it vice versa.

    Tree Planting strategy:
	Divide your initial cash into N parts and select N stocks. At the beginning,
    we do not have any shares in the account. We wait until one buying signal appear 
    in a certain stock, and buy the stock with one part of our initial cash. If the 
    price of the stock then falls under a certain ratio (ivar: stop_loss), stop out;
    otherwise if the price rises above a certain ratio (ivar: alive_point, it should 
    be small), we start to look for another buying signal in the rest N-1 stocks.
        With one stock in the account, we buy another stock when its buying signal 
    appears. Like the first one, we stop out if the price falls under a certain ratio;
    or prepare to buy the next stock if the price rises above a certain ratio. In the 
    meanwhile, sell any stock in the account if its selling signal appears.
        The rest can be done in the same manner. An important aspect here is we do not
    buy more than one stock at the same time, but we often try to buy more. This results 
    in the fact that we usually have more stocks during the bull and less stocks during 
    the bear, which is intriguing because we do not have to estimate when is bull and 
    when is bear: our account will tell us about that.

        The strategy is named 'tree planting' due to an interesting metaphor: imagine you
    account as a wooden land, each stock is a 'tree' and each part of your initial cash 
    is a bag of fertilizer. At the beginning, the land is bare (no tree exists). We wait 
    until one trading signal appear in a certain stock, which means 'a sapling is ready'.
    With the signal appear, we 'plant the sapling with one bag of our fertilizer'. If the 
    price of the stock then falls under a certain ratio (ivar: stop_loss), we say 'the tree
    is dead' and stop out; if the price rises above a certain ratio, we say 'the tree is 
    alive and ready to harvest'. The metaphor makes the strategy easier to remember.    
    """
    def __init__(self, name, N, stop_loss, alive_point):
	super(TreePlantingStrategy, self).__init__(name)
	self.N = N
	self.stop_loss = stop_loss
	self.alive_point = alive_point
	# const
	self.DEAD = 4444
	self.ALIVE = 8888

    @staticmethod
    def MACD(price, nslow = 26, nfast = 12, m = 9):
	emas = EMA(price, nslow)
	emaf = EMA(price, nfast)
	dif = emaf - emas
	dea = EMA(dif, m)
	macd = dif - dea
	return dif, dea, macd

    def compute_macd_for_all(self, stocks, n_ahead):
	self.macd = {} # {code(str): pd.DataFrame('dif', 'dea', index = datatime)}
        for code in stocks.keys():
	    cst = stocks[code].cst # get candlestick data

	    # MACD
	    dif, dea, _ = self.MACD(cst['1Day']['close'].values)

	    # skip extra data
	    TimeAxis = cst['1Day'].index[n_ahead:]
	    self.macd[code] = pd.DataFrame({'dif': dif[n_ahead:], 'dea': dea[n_ahead:]}, 
				     index = TimeAxis)

    def get_ready_saplings(self, stocks, ticker):
	"""
	Get ready saplings and update the start_flags of all stocks

	Returns:
	    return_codes(list): [code, ]
	"""
	ready_saplings = []
	for code in stocks.keys():
	    # skip null value at the beginning
	    try:
	        if np.isnan(self.macd[code].at[ticker, 'dif']) or np.isnan(self.macd[code].at[ticker, 'dea']):
	            continue 
	    except KeyError: # candlestick data is not available at this datetime
		continue
	    # skip the days of 'dif'>='dea' at the beginning
	    # those should be the days waiting fo selling, not buying, thus not suitable for a start
	    if (self.start_flags[code] == 0) and (self.macd[code].at[ticker, 'dif'] \
						>= self.macd[code].at[ticker, 'dea']):
                continue
	    else:
	        self.start_flags[code] = 1
	    # find buying signal
	    if (self.start_flags[code] == 1):
		if (self.state_flags[code] == 0) and (self.macd[code].at[ticker, 'dif'] \
						   > self.macd[code].at[ticker, 'dea']): 
		    ready_saplings.append(code)
	return ready_saplings

    def check_ready_to_buy(self, stocks):
	for code in stocks.keys():
	    if self.state_flags[code] == 1: # just planted yet
		return False
        # no False, then True
	return True

    def check_planting_sapling_status(self, planting_sapling, price, buy_price, ticker):
	assert(self.state_flags[planting_sapling] == 1)
	floating_ratio = (price - buy_price)/buy_price
	if floating_ratio < -self.stop_loss:
	    return self.DEAD
	elif floating_ratio > self.alive_point:
	    return self.ALIVE
		
    def init_stock_status(self, stocks, n_ahead):
	# compute MACD for all stocks
	# store in self.macd: {code(str): pd.DataFrame('dif', 'dea', index = datetime), }
        self.compute_macd_for_all(stocks, n_ahead)
	# to record status of stocks
	self.start_flags = {}
	self.state_flags = {}
	for code in stocks.keys():
	    self.start_flags[code] = 0 
	    self.state_flags[code] = 0
	    stocks[code].quantity = 0 # to store the quantity of stocks we have
	# Prepare ratios for the buy() functions so that the cash use by the
	# buy() functions are basically of the same amount.
	# for example, if N=10, then ratios = [1/10, 1/9, 1/8, ... , 1/2, 1]
	self.ratios = 1.0/np.arange(self.N,0,-1) 
	# to store the number of saplings (stocks) we have in the account
	self.n_saplings = 0 

    def compute_trading_points(self, stocks, szTimeAxis, n_ahead):
	assert len(stocks) >= self.N, \
		"This strategy requires at least N daily candlestick data of different stocks."
	self.init_stock_status(stocks, n_ahead)
	# start
	for ticker in szTimeAxis:
	    # try to plant saplings
	    if self.check_ready_to_buy(stocks): # are we planting a sapling now? do the following if not
	        ready_saplings = self.get_ready_saplings(stocks, ticker)
		if len(ready_saplings) > 0: 
		    planting_sapling = ready_saplings.pop(0)
		    price = stocks[planting_sapling].cst['1Day'].at[ticker,'close']
		    stocks[planting_sapling].quantity = buy(planting_sapling, price, str(ticker), \
						ratio = self.ratios[self.n_saplings])
		    stocks[planting_sapling].buy_price = price
		    self.state_flags[planting_sapling] = 1
		    self.n_saplings += 1
	    else: # we are planting a sapling
		try:	
		    price = stocks[planting_sapling].cst['1Day'].at[ticker,'close']
		    buy_price = stocks[planting_sapling].buy_price
		    status = self.check_planting_sapling_status(planting_sapling, price, buy_price, ticker)
		    # remove dead sapling   
		    if status == self.DEAD:
		        sell(planting_sapling, price, str(ticker), stocks[planting_sapling].quantity) 
		        self.state_flags[planting_sapling] = 0
		        self.n_saplings -= 1
		    # record alive sapling
		    if status == self.ALIVE:
		        self.state_flags[planting_sapling] = 2
		except KeyError: # candlestick data is not available at this datetime
		    pass
	    # try to harvest
	    for code in stocks.keys():
	        if (self.start_flags[code] == 1) and stocks[code].quantity > 0:
		    try:
	                if (self.state_flags[code] == 2) and (self.macd[code].at[ticker, 'dif'] \
						   < self.macd[code].at[ticker, 'dea']): 
			    price = stocks[code].cst['1Day'].at[ticker,'close']
		            sell(code, price, str(ticker), stocks[code].quantity) 
		            self.state_flags[code] = 0
		            self.n_saplings -= 1
		    except KeyError: # candlestick data is not available at this datetime
			pass


if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000049.dsdc-1Day', '000518.shsw-1Day', '000544.zyhb-1Day', '600004.byjc-1Day', \
    		'600038.zzgf-1Day', '600054.hsly-1Day', '600256.ghny-1Day', '600373.zwcm-1Day', \
    		'600867.thdb-1Day', '600085.trt-1Day']

    #pstocks = ['510050.50ETF-1Day', '510180.180ETF-1Day']
    #pstocks = ['000049.dsdc-1Day', '000518.shsw-1Day', '000544.zyhb-1Day', '600004.byjc-1Day', '600038.zzgf-1Day']

    # stop_loss: stop out when your loss of a sapling reach this proportion 
    stop_loss = 0.02
    # alive_point: if the floating earning of a sapling reach this proportion, we say it is 'alive'
    #              and we can sell it at a proper time.
    alive_point = 0.04
    # create a trading strategy
    strategy = TreePlantingStrategy('Tree Planting strategy', len(pstocks), stop_loss, alive_point)
    # set start and end datetime
    dt_start, dt_end = datetime(2004,7,1), datetime(2016,1,26)
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


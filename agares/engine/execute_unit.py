import ipdb
import os
import sys
import numpy as np
import pandas as pd
import math
from datetime import datetime
from agares.errors import FileDoesNotExist, NotEnoughMoney, BidTooLow, CanNotSplitShare, SellError
from agares.datastruct import PStock, StockID, parse_cst_filename
import matplotlib.pyplot as plt
from agares.io.output import Output


class ExecuteUnit(object):
    """
    Execute unit of a strategy.
    One execute unit can only load one strategy, and the period \
    candlestick data should all belong to one specific stock. 
    """
    def __init__(self, pstocks, dt_start, dt_end, n_ahead):
	self._strategy = None 
	# initial capital to invest, a constant once being set
	self._capital = 0
	# cash in the account, changing during the back test
	self._cash = 0
	# stock shares in the account, changing during the back test
	self._shares = {} # ._shares: {code(str): quantity(int)}
	# records. add one record after each transaction(buy or sell)
	# _records = [(datetime(str), cash, shares),]
	self._records = []
	# store total commission charge in the back test
	self._total_commission_charge = 0
	# store total stamp tax in the back test
	self._total_stamp_tax = 0
	# actual timescope of the back test, depending on the user setting and the available data 
	self.timescope = None
	# number of extra daily data for computation (ahead of start datatime)
	# set in the main program
	self.n_ahead = n_ahead
	# an output class instance for the report file
	self.o = None
	# check whether datetime is proper
	assert(dt_start < dt_end)
	# is_Day_cst: to check whether there is at least one daily candlestick data in pstocks
	is_Day_cst_exist = False
	# load candlestick(cst) data
	# .stocks = {code(str): PStock,}
	self.stocks = {}
	for pstock in pstocks:
	    # get info from filename 
	    # .ID: class StockID, .period: class PeriodInfo
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
	# trading_stocks: To store the stocks that are traded. Note that although have been loaded,
	#                 some stocks in self.stocks may not been traded in user's strategy.
	self.trading_stocks = set()


    def fill_missing_cst(self):
	""" 
	Find missing daily candlestick data and fill them 
	up in .stocks[code].missing_cst['1Day'] as pd.DataFrame 
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
	    # to store missing candlestick data of different period type
	    self.stocks[code].missing_cst = {}
	    # store missing cst as pd.DataFrame 
	    self.stocks[code].missing_cst['1Day'] = pd.DataFrame(tmp_cst, index = tmp_tickers)


    def add_strategy(self, strategy, settings = {}):
	"""
	Add the strategy and examine the settings
	"""
	self._strategy = strategy
	if settings:
	    # check and set capital
	    try:
		self._capital = settings['capital']
	        assert(settings['capital'] > 0)
	    except KeyError:
		print 'Capital unknown. Setting default to 10,000.'
		self._capital = 10000
	    finally:
		self._cash = self._capital
		self._records.append((self.timescope[0], self._cash, self._shares.copy()))
	    # check and set StampTaxRate
	    try:
		self.StampTaxRate = settings['StampTaxRate']
	        assert((0 <= settings['StampTaxRate']) & (settings['StampTaxRate'] < 1))
	    except KeyError:
		print 'StampTaxRate unknown. Setting default to 0.001.'
		self.StampTaxRate = 0.001
	    # check and set CommissionChargeRate
	    try:
		self.CommissionChargeRate = settings['CommissionChargeRate']
	        assert((0 <= settings['CommissionChargeRate']) & (settings['CommissionChargeRate'] < 1))
	    except KeyError:
		print 'CommissionChargeRate unknown. Setting default to 2.5e-4.'
		self.CommissionChargeRate = 2.5e-4

	# create an output instance for the strategy report
	root = os.path.join(os.getcwd(),'report')
	fname = self._strategy.name + ".report"
	self.o = Output(root, fname)

	    
    def run(self):
	print 'Running back test for the trading system..'
	self.o.report(' Blotter '.center(80, '='))
	try:
	    self._strategy.compute_trading_points(self.stocks, self.szTimeAxis, self.n_ahead)
	except BidTooLow:
	    self.o.report('[Abort] Your bid was too low for one board lot.')
	    self.o.report('Try increaing initial capital or buying position.')
	    return
	except NotEnoughMoney:
	    self.o.report('[Abort] No enough money to continue.')
	    return
	except CanNotSplitShare:
	    self.o.report('[Abort] You only have one share currently and can not be split.')
	    self.o.report('Examine your strategy or try set ratio in sell() to 1.')
	    return
	except SellError:
	    self.o.report('[Abort] Part of your sale does not exist.')
	    self.o.report('Please check your strategy.')
	    return

    def buy_ratio(self, code, price, datetime, ratio):
	"""
	Use this buy function if your want to invest with your profit  

	Args: 
	    datetime(str): trading time
	    ratio(float): the proportion of the current cash that you would like to bid. 	
			   Note that the current cash is the money in your account and would 
			   vary during the back test.
	"""
	# check
	assert(price > 0)
	assert((0 < ratio) and (ratio <= 1))
	# compute how many can we buy
	bid = self._cash * ratio
	# can we buy one board lot?
	oneboardlot = 100 * price # One board lot is 100 shares in Chinese market 
	if bid < oneboardlot: 
	    raise BidTooLow(need_cash = oneboardlot, bid = bid)
	if self._cash < oneboardlot: 
	    raise NotEnoughMoney(need_cash = oneboardlot, cash = self._cash)
	# can we buy more?
	quantity = int(math.floor(bid / oneboardlot))
	need_cash = quantity * oneboardlot # if run to here, we must have bid >= need_cash
	while self._cash < need_cash:
	    quantity = quantity - 1
	    need_cash = quantity * oneboardlot
	# now buy it
	self._cash -= need_cash
	try:	
	    self._shares[code] += quantity
	except KeyError:
	    self._shares[code] = quantity
        # commission charge deduction
	if (self.CommissionChargeRate > 0): # require consider commission charge
	    commission_charge = max(need_cash*self.CommissionChargeRate, 5) # at least 5 yuan 
	else: 
	    commission_charge = 0
        self._cash -= commission_charge
	# update total commission charge 
	self._total_commission_charge += commission_charge
	# add transaction record
	self._records.append((datetime, self._cash, self._shares.copy()))
	# print infomation
	self.o.report('- - '*20)
	self.o.report("[" + str(datetime) + "] ") 
	self.o.report("[stock code: {:s}]".format(code)) 
	self.o.report("Buy {0:d} board lot shares at price {1:.2f} (per share)".format(quantity, price))
	self.o.report("Commission charge: {:.2f}".format(commission_charge))
	self.o.report("Account: ")
	self.o.account(self._shares, self._cash)
	# return the number of shares (unit: boardlot) you buy this time 
	return quantity

    def buy_position(self, code, price, datetime, position):
	"""
	Use this buy function if you only want to invest with your capital, not profit

	Args: 
	    datetime(str): trading time
	    position(float): the proportion of the capital that you would like to bid. 	
			   Note that the capital is the initial money amount and is 
			   a constant once set at the beginning.
	"""
	# check
	assert(price > 0)
	assert((0 < position) and (position <= 1))
	# compute how many can we buy
	bid = self._capital * position
	# can we buy one board lot?
	oneboardlot = 100 * price # One board lot is 100 shares in Chinese market 
	if bid < oneboardlot: 
	    raise BidTooLow(need_cash = oneboardlot, bid = bid)
	if self._cash < oneboardlot: 
	    raise NotEnoughMoney(need_cash = oneboardlot, cash = self._cash)
	# can we buy more?
	quantity = int(math.floor(bid / oneboardlot))
	need_cash = quantity * oneboardlot # if run to here, we must have bid >= need_cash
	while self._cash < need_cash:
	    quantity = quantity - 1
	    need_cash = quantity * oneboardlot
	# now buy it
	self._cash -= need_cash
	try:	
	    self._shares[code] += quantity
	except KeyError:
	    self._shares[code] = quantity
        # commission charge deduction
	if (self.CommissionChargeRate > 0): # require consider commission charge
	    commission_charge = max(need_cash*self.CommissionChargeRate, 5) # at least 5 yuan 
	else: 
	    commission_charge = 0
        self._cash -= commission_charge
	# update total commission charge 
	self._total_commission_charge += commission_charge
	# add transaction record
	self._records.append((datetime, self._cash, self._shares.copy()))
	# print infomation
	self.o.report('- - '*20)
	self.o.report("[" + str(datetime) + "] ") 
	self.o.report("[stock code: {:s}]".format(code)) 
	self.o.report("Buy {0:d} board lot shares at price {1:.2f} (per share)".format(quantity, price))
	self.o.report("Commission charge: {:.2f}".format(commission_charge))
	self.o.report("Account: ")
	self.o.account(self._shares, self._cash)
	# return the number of shares (unit: boardlot) you buy this time 
	return quantity


    def sell(self, code, price, datetime, quantity):
	"""
	Args: 
	    datetime(str): trading time
	    quantity(int): the number of shares (unit: boardlot) you want to sell	
	"""
	# check
	assert(price > 0)
	assert(quantity >= 1)
	# now sell it
	income = quantity * price *100
	self._cash += income
	try:	
	    self._shares[code] -= quantity
	    if quantity < 0:
	        raise SellError
	except KeyError:
	    raise SellError
        # commission charge deduction
	if (self.CommissionChargeRate > 0): # require consider commission charge
	    commission_charge = max(income*self.CommissionChargeRate, 5) # at least 5 yuan 
	else: 
	    commission_charge = 0
        self._cash -= commission_charge
	# stamp tax deduction
	stamp_tax = income *self.StampTaxRate
	self._cash -= stamp_tax
	# update total commission charge 
	self._total_commission_charge += commission_charge
	# update total stamp tax 
	self._total_stamp_tax += stamp_tax
	# add transaction record
	self._records.append((datetime, self._cash, self._shares.copy()))
	# print infomation
	self.o.report('- - '*20)
	self.o.report("[" + str(datetime) + "] ") 
	self.o.report("[stock code: {:s}]".format(code)) 
	self.o.report("Sell {0:d} board lot shares at price {1:.2f} (per share)".format(quantity, price))
	self.o.report("Commission charge: {0:.2f},    Stamp Tax: {1:.2f}".format(commission_charge, stamp_tax))
	self.o.report("Account: ")
	self.o.account(self._shares, self._cash)

    def report(self):
	# operate: reportfile.seek(0)
	# We seek(0) the reportfile because we want these following statistics and performance results be
	# written at the beginning of the reportfile (we have left space for these contents in the file)
	self.o.seek(0)
	# now start writing report
	title = " Back Test Report "
	self.o.report(title.center(80, '='))
	dt_start, dt_end = self.timescope[0], self.timescope[1]
	self.o.report("Strategy: '{:s}'".format(self._strategy.name))
	self.o.report(self._strategy.__doc__)
	self.o.report("Time Scope: from {0:s} to {1:s}".format(dt_start, dt_end))
	self.o.report("Trading stocks: " + ",".join(self.trading_stocks)) # write down the stocks that had been traded
	self.o.report("Initial capital in account: cash[{:.2f}]".format(self._capital))
	self.o.report("Final equity in account: ")
        self.o.account(self._shares, self._cash)

	# create equity curve data 
        print "Creating equity curve data.."
        # see whether there is any transaction, if not, why bother
        if len(self._records) == 1: # that means no transaction
	    return
        # so there is some transactions. start creating equity curve
        # compute and store the state of the equity
        equity = []
        maxpeak = 0 # store the largest floating equity
        max_withdraw_ratio = 0 # store the largest withdraw ratio
	mwr_dt_start = None # store the start datetime of maximum withdraw ratio
	mwr_dt_end = None # store the end datetime of maximum withdraw ratio
        cur_ticker, cur_cash, cur_shares = self._records.pop(0)
        next_ticker, next_cash, next_shares = self._records.pop(0)
        next_ticker = datetime.strptime(next_ticker, "%Y-%m-%d %H:%M:%S") # datetime
        for ticker in self.szTimeAxis:
            ticker = datetime.strptime(str(ticker), "%Y-%m-%d %H:%M:%S") # datetime
            if ticker < next_ticker:
	        floating_equity = cur_cash
	        for code in cur_shares:
		    try:
		        price = self.stocks[code].cst['1Day'].at[ticker,'close']
		    except KeyError:
		        price = self.stocks[code].missing_cst['1Day'].at[ticker,'close']
                    cur_1boardlot_price = price *100
	            floating_equity += cur_shares[code] * cur_1boardlot_price
	        equity.append(floating_equity)
            else:
                cur_ticker, cur_cash, cur_shares = next_ticker, next_cash, next_shares
	        try:
	            next_ticker, next_cash, next_shares = self._records.pop(0)
	        except IndexError: # when reach the end of _records
		    next_ticker = self.timescope[1]
	        next_ticker = datetime.strptime(next_ticker, "%Y-%m-%d %H:%M:%S") # datetime
	        floating_equity = cur_cash
	        for code in cur_shares:
		    try:
		        price = self.stocks[code].cst['1Day'].at[ticker,'close']
		    except KeyError:
			price = self.stocks[code].missing_cst['1Day'].at[ticker,'close']
                    cur_1boardlot_price = price *100
	            floating_equity += cur_shares[code] * cur_1boardlot_price
	        equity.append(floating_equity)
	    # update maxpeak, mwr_dt_start, mwr_dt_end
	    if floating_equity > maxpeak:
	        maxpeak = floating_equity
		temp_mwr_dt_start = str(ticker)
	    else: 
	        withdraw = maxpeak - floating_equity
	        # update maximum withdraw ratio 
	        if withdraw/maxpeak > max_withdraw_ratio:
		    max_withdraw_ratio = withdraw/maxpeak
		    mwr_dt_start, mwr_dt_end = temp_mwr_dt_start, str(ticker)
        # continue writing report: 
	self.o.report("Final equity convert into cash: {:.2f}".format(equity[-1]))
	profit = equity[-1] -equity[0]
	self.o.report("Profit: {:.2f}".format(profit))
	rate_of_return = profit/self._capital
	self.o.report("Rate of return: {:.2f}%".format(rate_of_return*100))
	# get time span
	dt_start = datetime.strptime(str(dt_start), "%Y-%m-%d %H:%M:%S") # datetime
	dt_end = datetime.strptime(str(dt_end), "%Y-%m-%d %H:%M:%S") # datetime
	time_span_days = (dt_end -dt_start).days
	time_span_years = time_span_days/365.0
	annualized_return = math.exp(math.log(1 + rate_of_return)/19)-1
	self.o.report("Annualized Return (compound interest): {:.2f}%".format(annualized_return*100))
	self.o.report("Maximum withdraw ratio: {:.2f}%".format(max_withdraw_ratio*100))
	self.o.report("The start datetime of maximum withdraw ratio: {:s}".format(mwr_dt_start))
	self.o.report("The end datetime of maximum withdraw ratio: {:s}".format(mwr_dt_end))
	self.o.report("Commission Charge: {:.2f}".format(self._total_commission_charge))
	self.o.report("Stamp Tax: {:.2f}".format(self._total_stamp_tax))
	# Done writing report
	self.o.close()
        # return df_equity(pd.DataFrame)
	df_equity = pd.DataFrame({'equity': equity, 'sz': self.sz_daily_close}, index = self.szTimeAxis)
	return df_equity

	    







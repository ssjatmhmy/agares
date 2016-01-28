import ipdb
import os
import numpy as np
import pandas as pd
import math
from datetime import datetime
from agares.errors import FileDoesNotExist, NotEnoughMoney, BidTooLow, CanNotSplitShare
from agares.datastruct import PStockInfo
import matplotlib.pyplot as plt
from agares.io.output import Output

class ExecuteUnit(object):
    """
    Execute unit of a strategy.
    One execute unit can only load one strategy, and the period \
    candlestick data should all belong to one specific stock. 
    """
    def __init__(self, mpstock, dt_start, dt_end, n_ahead):
	self._strategy = None 
	# initial capital to invest, a constant once being set
	self._capital = 0
	# cash in the account, changing during the back test
	self._cash = 0
	# stock shares in the account, changing during the back test
	self._shares = int(0)
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
	# number of actual extra daily data. 
	# It would be smaller than n_ahead due to lack of data
	self.actual_ahead = None 
	# load stock info
	pstockinfo = PStockInfo(mpstock[0])
	self.stock = str(pstockinfo.stock)	
	self.stock_code = pstockinfo.stock.code
	self.stock_name = pstockinfo.stock.name
	# an output class instance for the report file
	self.o = None
	# check whether datetime is proper
	assert(dt_start < dt_end)
	# load candlestick(cst) data
	# cst = {str(pstock): pd.DataFrame(datetime, open, close, high, low, volume, ..),}
	self.cst = {} 
	for pstock in mpstock:
	    self.load_cst(pstock, dt_start, dt_end, n_ahead)

    def load_cst(self, pstock, dt_start, dt_end, n_ahead):	    
        """
        Args:
	    pstock(str): period candlestick data filename
	    dt_start(datetime): start time
	    dt_end(datetime): end time
	Returns:
	    pd.DataFrame, i.e., candlestick data
  	"""
	pstockinfo = PStockInfo(pstock)
	ptype = pstockinfo.period.type
	try:
	    return self.cst[ptype]
	except KeyError:
	    root = os.path.join(os.getcwd(),'data')
	    fname = os.path.join(root, str(pstock) + ".csv")
	    try:
	        cst_data = pd.read_csv(fname, index_col = 0, parse_dates = True, sep=' ')
	    except IOError:
		raise FileDoesNotExist(file = fname)
	    else:
		# select data
		dt_start = pd.to_datetime(dt_start)
		dt_end = pd.to_datetime(dt_end)
		index = np.arange(len(cst_data.index))
		select = index[(dt_start <= cst_data.index) & (cst_data.index <= dt_end)]
		# read candlestick data timescope
		self.timescope = str(cst_data.index[select[0]]), str(cst_data.index[select[-1]])	
		# add (n_head) extra data for strategy computation 
		start_index = max(select[0] - n_ahead, 0)
		actual_ahead = select[0] - start_index
		end_index = select[-1] + 1
		cst_data = cst_data.iloc[start_index: end_index]
		assert cst_data.index.is_unique
		# load data
		self.cst[ptype] = cst_data
		self.actual_ahead = actual_ahead

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
		self._records.append((self.timescope[0], self._cash, self._shares))
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
	fname = self._strategy.name + "." + self.stock + ".report"
	self.o = Output(root, fname)

	    
    def run(self):
	print 'Running back test for the trading system..'
	self.o.printsf(' Blotter '.center(80, '='))
	try:
	    self._strategy.compute_trading_points(self.cst, self.actual_ahead)
	except BidTooLow:
	    self.o.printsf('[Abort] Your bid was too low for one board lot.')
	    self.o.printsf('Try increaing initial capital or buying position.')
	    return
	except NotEnoughMoney:
	    self.o.printsf('[Abort] No enough money to continue.')
	    return
	except CanNotSplitShare:
	    self.o.printsf('[Abort] You only have one share currently and can not be split.')
	    self.o.printsf('Examine your strategy or try set ratio in sell() to 1.')
	    return

    def buy_ratio(self, price, datetime, ratio):
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
	self._shares += quantity
        # commission charge deduction
	commission_charge = max(need_cash*self.CommissionChargeRate, 5) # at least 5 yuan 
        self._cash -= commission_charge
	# update total commission charge 
	self._total_commission_charge += commission_charge
	# add transaction record
	self._records.append((datetime, self._cash, self._shares))
	# print infomation
	self.o.printsf('- - '*20)
	self.o.printsf("[" + str(datetime) + "] " + 
			"Buy {0:d} board lot shares at price {1:.2f} (per share)".format(quantity, price))
	self.o.printsf("Commission charge: {:.2f}".format(commission_charge))
	self.o.printsf("Account: share[{0:d} Board Lot], cash[{1:.2f}]".format(self._shares, self._cash))
	# return the number of shares (unit: boardlot) you buy this time 
	return quantity

    def buy_position(self, price, datetime, position):
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
	self._shares += quantity
        # commission charge deduction
	commission_charge = max(need_cash*self.CommissionChargeRate, 5) # at least 5 yuan 
        self._cash -= commission_charge
	# update total commission charge 
	self._total_commission_charge += commission_charge
	# add transaction record
	self._records.append((datetime, self._cash, self._shares))
	# print infomation
	self.o.printsf('- - '*20)
	self.o.printsf("[" + str(datetime) + "] " + 
			"Buy {0:d} board lot shares at price {1:.2f} (per share)".format(quantity, price))
	self.o.printsf("Commission charge: {:.2f}".format(commission_charge))
	self.o.printsf("Account: share[{0:d} Board Lot], cash[{1:.2f}]".format(self._shares, self._cash))
	# return the number of shares (unit: boardlot) you buy this time 
	return quantity


    def sell(self, price, datetime, quantity):
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
	self._shares -= quantity
        # commission charge deduction
	commission_charge = max(income*self.CommissionChargeRate, 5) # at least 5 yuan 
        self._cash -= commission_charge
	# stamp tax deduction
	stamp_tax = income *self.StampTaxRate
	self._cash -= stamp_tax
	# update total commission charge 
	self._total_commission_charge += commission_charge
	# update total stamp tax 
	self._total_stamp_tax += stamp_tax
	# add transaction record
	self._records.append((datetime, self._cash, self._shares))
	# print infomation
	self.o.printsf('- - '*20)
	self.o.printsf("[" + str(datetime) + "] " + 
			"Sell {0:d} board lot shares at price {1:.2f} (per share)".format(quantity, price))
	self.o.printsf("Commission charge: {0:.2f},    Stamp Tax: {1:.2f}".format(commission_charge, stamp_tax))
	self.o.printsf("Account: share[{0:d} Board Lot], cash[{1:.2f}]".format(self._shares, self._cash))

    def report(self):
	# operate: reportfile.seek(0)
	# We seek(0) the reportfile because we want these following statistics and performance results be
	# written at the beginning of the reportfile (we have left space for these contents in the file)
	self.o.seek(0)
	# now start writing report
	title = " Back Test Report "
	self.o.printsf(title.center(80, '='))
	dt_start, dt_end = self.timescope[0], self.timescope[1]
	self.o.printsf("Strategy: '{:s}'".format(self._strategy.name))
	self.o.printsf(self._strategy.__doc__)
	self.o.printsf("Time Scope: from {0:s} to {1:s}".format(dt_start, dt_end))
	self.o.printsf("Stock: {:s}".format(self.stock))
	self.o.printsf("Initial capital in account: cash[{:.2f}]".format(self._capital))
	self.o.printsf("Final equity in account: share[{0:d} Board Lot], cash[{1:.2f}]".format(self._shares, self._cash))

	# create equity curve data if daily candlestick data is available
	try:
	    df_1day = self.cst['1Day'] # pd.DataFrame
	except KeyError:
	    print "Pass plotting the equity curve: the daily candlestick data is not provided."
	    pass
	else:
	    print "Creating equity curve data.."
	    # see whether there is any transaction, if not, why bother
	    if len(self._records) == 1: # that means no transaction
		return
	    # so there is some transactions. start create equity curve
	    # load price data
	    datetime_1day = df_1day.index
	    close_1day = df_1day['close'].values
	    # compute and store the state of the equity
	    equity = []
	    maxpeak = 0 # store the largest floating equity
	    max_withdraw = 0 # store the largest withdraw
	    max_withdraw_ratio = 0 # store the largest withdraw ratio
	    cur_ticker, cur_cash, cur_shares = self._records.pop(0)
	    next_ticker, next_cashp, next_shares = self._records.pop(0)
	    next_ticker = datetime.strptime(next_ticker, "%Y-%m-%d %H:%M:%S") # datetime
	    for i, ticker in enumerate(df_1day.index):
	        ticker = datetime.strptime(str(ticker), "%Y-%m-%d %H:%M:%S") # datetime
	        if ticker < next_ticker:
	            cur_1boardlot_price = close_1day[i] *100
		    floating_equity = cur_cash + cur_shares * cur_1boardlot_price
		    equity.append(floating_equity)
	        else:
  	            cur_ticker, cur_cash, cur_shares = next_ticker, next_cashp, next_shares
		    try:
		        next_ticker, next_cashp, next_shares = self._records.pop(0)
		    except IndexError: # when reach the end of _records
			next_ticker = self.timescope[1]
		    next_ticker = datetime.strptime(next_ticker, "%Y-%m-%d %H:%M:%S") # datetime
		    cur_1boardlot_price = close_1day[i] *100
    		    floating_equity = cur_cash + cur_shares * cur_1boardlot_price
		    equity.append(floating_equity)
		# update maxpeak
		if floating_equity > maxpeak:
		    maxpeak = floating_equity
		else: 
		    withdraw = maxpeak - floating_equity
		    # update maximum withdraw 
		    if withdraw > max_withdraw:
			max_withdraw = withdraw
		    # update maximum withdraw ratio 
		    if withdraw/maxpeak > max_withdraw_ratio:
			max_withdraw_ratio = withdraw/maxpeak
        # continue writing report: 
	self.o.printsf("Final equity convert into cash: {:.2f}".format(equity[-1]))
	profit = equity[-1] -equity[0]
	self.o.printsf("Profit: {:.2f}".format(profit))
	self.o.printsf("Rate of return: {:.2f}%".format(profit/self._capital*100))
	self.o.printsf("Maximum withdraw: {:.2f}".format(max_withdraw))
	self.o.printsf("Maximum withdraw ratio: {:.2f}%".format(max_withdraw_ratio*100))
	self.o.printsf("Commission Charge: {:.2f}".format(self._total_commission_charge))
	self.o.printsf("Stamp Tax: {:.2f}".format(self._total_stamp_tax))

	# Done writing report
	self.o.close()
        # return df_equity(pd.DataFrame)
	df_equity = pd.DataFrame({'equity': equity}, index = datetime_1day)
	return df_equity

	    







import ipdb
from datetime import datetime
from agares.engine.execute_unit import ExecuteUnit
import matplotlib.pyplot as plt
from abc import ABCMeta, abstractmethod
import pandas as pd

# global
ag_simulator = None

def create_trading_system(strategy, pstocks, dt_start, dt_end, n_ahead, capital, StampTaxRate, CommissionChargeRate):
    """
    Create a trading system

    Args:
    	pstocks([str,]): list of candlestick data files, each item represents \             
                         a period data of a interested stock
    	dt_start(str): start datetime
    	dt_end(str): end datetime
        n_ahead(int): Number of extra daily data. We add extra daily data (before start date) for computing 
		      indexes such as MA, MACD. These may help to avoid nan at the beginning of indexes.
    """
    global ag_simulator
    ag_simulator = ExecuteUnit(pstocks, dt_start, dt_end, n_ahead, capital, StampTaxRate, CommissionChargeRate)
    ag_simulator.add_strategy(strategy)


def run():
    ag_simulator.run()


def buy(code, price, datetime, **kargs):
    """
    Args: 
	kargs(optional): You have two choices, position or ratio (both within (0,1])
			 Below are some detail descriptions.

        		 position(float): the proportion of the capital that you would like to bid. 	
		                          Note that the capital is the initial money amount and is 
		                          a contant once set at the beginning.
			 ratio(float): the proportion of the current cash that you would like to bid. 	
			               Note that the current cash is the money in your account and 
				       would vary during the back test.
    Return:
	quantity(int): the number of shares (unit: boardlot) you buy this time
    """
    if kargs.has_key('ratio'):
	quantity = ag_simulator.buy_ratio(code, price, datetime, ratio = kargs['ratio'])  
    elif kargs.has_key('position'):   
        quantity = ag_simulator.buy_position(code, price, datetime, position = kargs['position']) 
    else:
	print "Warning: ratio/position not given in buy(). Using default: position = 1."
	quantity = ag_simulator.buy_position(code, price, datetime, position = 1) 
    ag_simulator.trading_stocks.add(code)
    return quantity


def sell(code, price, datetime, quantity):
    """
    Args: 
        datetime(str): trading time
        quantity(int): the number of shares (unit: boardlot) you want to sell	
    """
    ag_simulator.sell(code, price, datetime, quantity)
    ag_simulator.trading_stocks.add(code)


def report(PlotEquity = False, PlotNetValue = False):
    """
    Report performance of the trading system

    Args:
	PlotEquity(boolean): If True, a simple graph of equity curve will be drawn.
	PlotNetValue(boolean): If True, a net value curve of the strategy will be 
			       drawn along with a scaled sz daily close price curve.
    """
    df_equity = ag_simulator.report()
    if PlotEquity: # plot equity
        df_equity['equity'].plot()
    	print "Plot of equity curve is shown."
    	plt.show()
    if PlotNetValue:
	init_equity = df_equity['equity'].values[0]
	init_sz = df_equity['sz'].values[0]
	net_value = df_equity['equity'].values/float(init_equity)
	scaled_sz = df_equity['sz'].values/float(init_sz)
	df_nv = pd.DataFrame({'Net value': net_value, 'scaled sz': scaled_sz}, index = df_equity.index)
	df_nv.plot()
	print "Plot of net value curve is shown."
	plt.show()
    return df_equity
	


class Strategy(object):
    """
    Base class of strategy
    """
    __metaclass__ = ABCMeta

    def __init__(self, name):
	self.name = name

    @abstractmethod
    def compute_trading_points(self, stocks, szTimeAxis, n_ahead):
	"""
	Args:
	    stocks: {code(str): PStock, }, where
		    class PStock has the following members for user

		    PStock.cst: {period(str): pd.DataFrame(datetime, open, close, high, low, volume, ..), }
				to store candlestick data of different periods. 'cst' is short for 'candlestick'
		    PStock.missing_cst: {period(str): pd.DataFrame(datetime, open, close, high, low, volume, ..), }
                                similar to .cst, it stores the missing candlestick data of different period type.
				The reason that cause the missing cst would be stock suspension or something else.
        	    PStock.ID: class StockID, which has two member: .code(str) and .name(str)

		    Note that both .cst and .missing_cst contain n_ahead extra daily data (see the description of 
		    n_ahead).
	    szTimeAxis(pd.DateTimeIndex): Time axis of sz, from dt_start to dt_end.
            n_ahead(int): Number of extra daily data. We add extra daily data (before start date) for computing 
			  indexes such as MA, MACD. These may help to avoid nan at the beginning of indexes.
	"""
	pass


def ask_agares(settings):
    """
    Do all the back-testing work, including checking settings, creating trading system, 
    running the back-testing, and generating report.

    Args: 
	settings: {name(str): setting, }. a dictionary that includes all settings that agares needs. The items 
                  are as follows:

                  'pstocks': pstocks(list), list of candlestick data files, each item represents a period data of a 
		             interested stock. pstocks could contain multiple stock of multiple type of period.
		  'strategy': strategy(class Strategy), a trading strategy. It should be a subclass instance of the 
                              Strategy class.
		  'dt_start': dt_start(datetime), start datetime
		  'dt_end': dt_end(datetime), end datetime
    		  'n_ahead': n_ahead(int), number of extra daily data for computation (ahead of start datatime). We 
			      add extra daily data (before start date) for computing indexes such as MA, MACD. These 
                              may help to avoid nan at the beginning of indexes.
		  'capital': capital(float), Initial money for investment.
		  'StampTaxRate': StampTaxRate(float), Usually 0.001. Only charge when sell. The program do not consider 
				  the fact that buying funds do not charge this tax. So set it to 0 if the 'pstocks' 
				  are ETF funds.
		  'CommissionChargeRate': CommissionChargeRate(float), Usually 2.5e-4. The fact that commission charge 
					is at least 5 yuan has been considered in the program.
		  'PlotNetValue': PlotNetValue(boolean), If True, a net value curve of the strategy will be drawn along 
				  with a scaled sz daily close price curve after the back-testing.
		  'PlotEquity': PlotEquity(boolean), If True, a simple graph of equity curve will be drawn after the 
				back-testing.
		  'ReturnEquity': ReturnEquity(boolean), Set to True if you want agares to return the variable df_equity 
				  (pd.DataFrame), which can be used to draw equity curve. 
    """
    strategy = settings['strategy']
    pstocks = settings['pstocks']
    dt_start = settings['dt_start'] 
    dt_end = settings['dt_end'] 
    n_ahead = settings['n_ahead']
    # check and set capital
    try:
	capital = settings['capital']
	assert(settings['capital'] > 0)
    except KeyError:
	print 'Capital unknown. Setting default to 10,000.'
	capital = 10000
    # check and set StampTaxRate
    try:
	StampTaxRate = settings['StampTaxRate']
        assert((0 <= settings['StampTaxRate']) & (settings['StampTaxRate'] < 1))
    except KeyError:
	print 'StampTaxRate unknown. Setting default to 0.001.'
	StampTaxRate = 0.001
    # check and set CommissionChargeRate
    try:
	CommissionChargeRate = settings['CommissionChargeRate']
        assert((0 <= settings['CommissionChargeRate']) & (settings['CommissionChargeRate'] < 1))
    except KeyError:
	print 'CommissionChargeRate unknown. Setting default to 2.5e-4.'
	CommissionChargeRate = 2.5e-4
    # check and set report parameters
    try:
	ReturnEquity = settings['ReturnEquity']
    except KeyError:
	ReturnEquity = False
    try:
	PlotEquity = settings['PlotEquity']
    except KeyError:
	PlotEquity = False
    try:
	PlotNetValue = settings['PlotNetValue']
    except KeyError:
	PlotNetValue = False
    # create a trading system
    create_trading_system(strategy, pstocks, dt_start, dt_end, n_ahead, capital, StampTaxRate, CommissionChargeRate)
    # start back testing
    run()
    # report performance of the trading system
    df_equity = report(PlotEquity, PlotNetValue)
    if ReturnEquity:
        return df_equity






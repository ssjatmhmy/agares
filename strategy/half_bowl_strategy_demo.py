# @file half_bowl_strategy_demo.py
# @brief half bowl strategy demo

import ipdb
from talib import (MA, EMA)
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
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


class HalfBowlStrategy(Strategy):
    """ 
    The half bowl strategy on daily candlestick data.
    Divide your initial cash into two equal parts and use one part to buy shares at the first day.
    If the price of your shares falls (ivar:fall_ratio), use the cash to buy more and make two\
    parts of the equities even again. If the price of your shares rises (ivar:rise_ratio), sell \
    some of them to make two parts of the equities even again. 
    """
    def __init__(self, name, rise_ratio, fall_ratio):
        super(HalfBowlStrategy, self).__init__(name)
        self.rise_ratio = rise_ratio
        self.fall_ratio = fall_ratio

    def compute_trading_points(self, stocks, szTimeAxis, n_ahead):
        assert len(stocks) == 1, "This strategy allows only a daily candlestick data of one stock."
        code = next(iter(stocks))
        cst = stocks[code].cst # get candlestick data
        DataTimeAxis = cst['1Day'].index

        # skip extra data
        TimeAxis = DataTimeAxis[n_ahead:]

        # buy with half capital at the first day
        ticker = TimeAxis[0]
        price = cst['1Day'].at[ticker,'close']
        _, shares, cash = buy(code, price, str(ticker), ratio = 0.5) 
        share = shares[code]
        # start trading
        for ticker in TimeAxis[1:]:
            price = cst['1Day'].at[ticker,'close']
            oneboardlot = 100 * price # One board lot is 100 shares in Chinese market 
            stock_equity = share * oneboardlot
            if (stock_equity <= cash*(1-self.fall_ratio)): 
                # make even: make the stock equity approximate to current cash
                _, shares, cash = buy(code, price, str(ticker), cash = (cash-stock_equity)/2.0) 
                share = shares[code]
            if (stock_equity >= cash*(1+self.rise_ratio)):
                quantity_to_sell = int((stock_equity-cash)/2.0/oneboardlot)
                # make even: make the stock equity approximate to current cash
                shares, cash = sell(code, price, str(ticker), quantity_to_sell)
                share = shares[code]


if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create a trading strategy
    rise_ratio, fall_ratio = 0.2, 0.2
    strategy = HalfBowlStrategy('Half bowl strategy', rise_ratio, fall_ratio)
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




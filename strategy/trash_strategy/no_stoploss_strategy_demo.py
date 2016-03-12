# @file no_stoploss_strategy_demo.py
# @brief no stoploss strategy demo

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


class NoStoplossStrategy(Strategy):
    """ 
    The no stoploss strategy on daily candlestick data.
    No sell unless reach the required earning ratio. 
    """
    def __init__(self, name, level, rise_ratio, fall_ratio):
        super(NoStoplossStrategy, self).__init__(name)
        self.level = level
        self.rise_ratio = rise_ratio
        self.fall_ratio = fall_ratio

    @staticmethod
    def MACD(price, nslow=26, nfast=12, m=9):
        emas = EMA(price, nslow)
        emaf = EMA(price, nfast)
        dif = emaf - emas
        dea = EMA(dif, m)
        macd = dif - dea
        return dif, dea, macd
        
    def compute_trading_points(self, stocks, szTimeAxis, n_ahead):
        assert len(stocks) == 1, "This strategy allows only a daily candlestick data of one stock."
        code = next(iter(stocks))
        cst = stocks[code].cst # get candlestick data
        DataTimeAxis = cst['1Day'].index

        # MACD
        dif, dea, _ = self.MACD(cst['1Day']['close'].values)

        # skip extra data
        TimeAxis = DataTimeAxis[n_ahead:]
        df_macd = pd.DataFrame({'dif': dif[n_ahead:], 'dea': dea[n_ahead:]}, 
                    index = TimeAxis)

        # start trading
        start_flag, state_flag = 0, 0
        for ticker in TimeAxis:
            # skip null value at the beginning
            if np.isnan(df_macd.at[ticker, 'dif']) or np.isnan(df_macd.at[ticker, 'dea']):
                continue 
            # Skip the days of 'dif'>='dea' at the beginning. Those should be the days waiting for \
            # selling, not buying, thus not suitable for a start
            if (start_flag == 0) and (df_macd.at[ticker, 'dif'] >= df_macd.at[ticker, 'dea']):
                continue
            else:
                start_flag = 1
                
            # start trading
            if (start_flag == 1):
                price = cst['1Day'].at[ticker,'close']
                oneboardlot = 100 * price # One board lot is 100 shares in Chinese market 
                # the first buying
                if (state_flag == 0) and (price <= self.level) and\
                                         (df_macd.at[ticker, 'dif'] > df_macd.at[ticker, 'dea']): 
                    quantity, shares, cash = buy(code, price, str(ticker), ratio=0.5)
                    stock_equity = shares[code] * oneboardlot  
                    cost = quantity * oneboardlot
                    state_flag = 1
                    continue
                # the second buying if price falls
                if (state_flag == 1) and (stock_equity < cost*(1-self.fall_ratio)):
                    quantity, shares, cash = buy(code, price, str(ticker), ratio=1)
                    cost += quantity * oneboardlot
                    state_flag = 2
                    continue
                # sell                                        
                if (state_flag >= 1) and (df_macd.at[ticker, 'dif'] <= df_macd.at[ticker, 'dea']):
                    if (shares[code]*oneboardlot > cost*(1+self.rise_ratio)): 
                        shares, cash = sell(code, price, str(ticker), shares[code])
                        state_flag = 0
                        continue


if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create a trading strategy
    level, rise_ratio, fall_ratio = 3000, 0.4, 0.2
    strategy = NoStoplossStrategy('No stoploss strategy', level, rise_ratio, fall_ratio)
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




# @file RF_and_GBDT_for_cst_demo.py
# @brief predict stock price (rise or fall) with Random Forest (RF) and GBDT algorithm on cst data

import ipdb
import numpy as np
import pandas as pd
from talib import (MA, EMA)
import matplotlib.pyplot as plt
from time import time
from datetime import datetime, timedelta
import os
fdir = os.path.split(os.path.realpath(__file__))[0]
root = os.path.split(os.path.split(fdir)[0])[0]
import sys 
sys.path.append(root)
from agares.engine.ag import (
    Analysis,
    ask_agares)
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

class RFandGBDTforCstAnalysis(Analysis):
    """ 
    predict stock price (rise or fall) with Random Forest (RF) and GBDT algorithm on cst data.
    """
    def __init__(self, name):
        super(RFandGBDTforCstAnalysis, self).__init__(name)
   
    @staticmethod
    def MACD(price, nslow=26, nfast=12, m=9):
        emas = EMA(price, nslow)
        emaf = EMA(price, nfast)
        dif = emaf - emas
        dea = EMA(dif, m)
        macd = dif - dea
        return dif, dea, macd
        
    @staticmethod
    def ChangeRatio(vec):
        """
        Compute (value[i]-value[i-1])/value[i-1] for each value in vec. 
        Note that the first value of the return vector is meaningless. 
        
        Args:
            vec(np.array), should be a vector
        Returns:
            (np.array), a vector of the same size of vec
        """
        change = np.zeros(len(vec))
        change[1:] = np.diff(vec)
        pvec = np.ones(len(vec))
        pvec[1:] = vec[:-1]
        return change/pvec
        
    @staticmethod
    def ChangeRatioAverage(vec, n):
        """
        Compute (value[i]-aver(value[i-n:i]))/aver(value[i-n:i]) for each value in vec, where \
        aver() means compute average of its inputs. Note that 1) value[i] is not included in \
        computing the average; 2) the first n value of the return vector is meaningless. 
        
        Args:
            vec(np.array), should be a vector
        Returns:
            (np.array), a vector of the same size of vec
        """
        sum_pvec = np.zeros(len(vec))
        for i in range(n):
            pvec = np.ones(len(vec))
            pvec[i+1:] = vec[:-i-1]
            sum_pvec += pvec 
        aver_pvec = sum_pvec/float(n)
        return (vec-aver_pvec)/aver_pvec
        
    def generate_data(self, cst_d, n_ahead):
        """ 
        Generate data for ML algorithms from cst data.
        
        Returns:
            df_data(pd.dataframe), with index of pd.TimeStamp type
            
            the feature columns of train_data are:
            ['close', 'PriceChangeRatio', 'dif', 'dea', 'macd', 'ma5', 'ma10', 'ma20', 'ma5-ma10', \
            'ma5-ma20', 'ma10-ma20', 'vol', 'VolChangeRatio', 'VolChangeRatioAverage']
            and labels/turnouts of train_data are:
            ['after1d', 'after2d', 'after3d', 'after4d', 'after5d', 'after5dRise?', \
            'after5dChange2%?', 'after3dChangeRatio', 'after5dChangeRatio']
        """
        # get time axis of the cst data
        DataTimeAxis = cst_d.index
        # PriceChangeRatio feature
        price_change_ratio = self.ChangeRatio(cst_d['close'].values)
        # MACD feature
        dif, dea, macd = self.MACD(cst_d['close'].values)
        # Moving average features
        ma5 = MA(cst_d['close'].values, 5)
        ma10 = MA(cst_d['close'].values, 10)
        ma20 = MA(cst_d['close'].values, 20)
        ma5_ma10 = ma5 - ma10
        ma5_ma20 = ma5 - ma20
        ma10_ma20 = ma10 - ma20
        # VolChangeRatio feature
        vol_change_ratio = self.ChangeRatio(cst_d['volume'].values)
        # VolChangeRatioAverage: vol vs that of the average of pass 5 days
        vol_change_ratio_aver = self.ChangeRatioAverage(cst_d['volume'].values, 5)
        # skip extra data and create feature dataframe
        TimeAxis = DataTimeAxis[n_ahead:]
        cst_v = cst_d['close'].values[n_ahead:]
        df_features = pd.DataFrame({'close': cst_v}, index = TimeAxis)
        df_features = df_features.join(pd.DataFrame({'dif': dif[n_ahead:], 'dea': dea[n_ahead:], \
                                        'macd': macd[n_ahead:]}, index = TimeAxis))
        df_features = df_features.join(pd.DataFrame({'ma5': ma5[n_ahead:], 'ma10': ma10[n_ahead:], \
            'ma20': ma20[n_ahead:], 'ma5-ma10': ma5_ma10[n_ahead:],'ma5-ma20': ma5_ma20[n_ahead:],\
             'ma10-ma20': ma10_ma20[n_ahead:]}, index = TimeAxis))
        df_features['PriceChangeRatio'] = price_change_ratio[n_ahead:]
        df_features['VolChangeRatio'] = vol_change_ratio[n_ahead:]
        df_features['VolChangeRatioAverage'] = vol_change_ratio_aver[n_ahead:]
        df_features['vol'] = cst_d['volume'].values[n_ahead:]
        # to store tickers of the train data
        tmp_tickers = []
        # to store features of the train data
        turnout = ['after1d', 'after2d', 'after3d', 'after4d', 'after5d', 'after5dRise?', \
                    'after5dChange2%?', 'after3dChangeRatio', 'after5dChangeRatio']
        tmp_turnout = {column: [] for column in turnout}
        # flags. 'dc' is short for 'dead cross'; 'gc' is short for 'golden cross' 
        wait_dc, wait_gc = False, False        
        # start selecting useful data
        for i, ticker in enumerate(TimeAxis):
            # skip null value at the beginning
            if np.isnan(df_features.at[ticker, 'dif']) or np.isnan(df_features.at[ticker, 'dea']):
                continue
            # if golden cross or dead cross
            if ((wait_dc is True) and \
                                (df_features.at[ticker, 'dif'] < df_features.at[ticker, 'dea']))\
                or ((wait_gc is True) and \
                                (df_features.at[ticker, 'dif'] > df_features.at[ticker, 'dea'])):
                # record useful data
                tmp_tickers.append(ticker)
                for day, column in enumerate(turnout[:5], start=1):
                    tmp_turnout[column].append(cst_v[i+day])
                after3dChangeRatio = (cst_v[i+3] - cst_v[i])/cst_v[i]
                tmp_turnout['after3dChangeRatio'].append(after3dChangeRatio)
                after5dChangeRatio = (cst_v[i+5] - cst_v[i])/cst_v[i]
                tmp_turnout['after5dChangeRatio'].append(after5dChangeRatio)
                if after5dChangeRatio >= 0.02:
                    tmp_turnout['after5dChange2%?'].append('rise2%')
                elif after5dChangeRatio <= -0.02:
                    tmp_turnout['after5dChange2%?'].append('fall2%')
                else:
                    tmp_turnout['after5dChange2%?'].append('within2%')
                if after5dChangeRatio > 0:
                    tmp_turnout['after5dRise?'].append('yes')
                elif after5dChangeRatio <= 0:
                    tmp_turnout['after5dRise?'].append('no')
            # change state
            if df_features.at[ticker, 'dif'] > df_features.at[ticker, 'dea']:
                wait_dc, wait_gc = True, False
            if df_features.at[ticker, 'dif'] < df_features.at[ticker, 'dea']:
                wait_dc, wait_gc = False, True
        # create data
        df_data = df_features.loc[tmp_tickers,:]
        df_data = df_data.join(pd.DataFrame(tmp_turnout, index=tmp_tickers))
        return df_data
                
    def perform_analysis(self, stocks, szTimeAxis, n_ahead):
        assert len(stocks) == 1, "This analysis allows only a daily candlestick data of one stock."
        code = next(iter(stocks))
        cst_d = stocks[code].cst['1Day'] # get daily candlestick data
        # generate train data
        df_data = self.generate_data(cst_d, n_ahead)
        # Data preprocessing: 
        # drop some useless columns; do some data format transformation 
        drop_columns = ['dif', 'dea', 'ma5', 'ma10', 'ma20', 'after1d', 'after2d', 'after3d',\
                        'vol', 'after4d', 'after5d', 'after5dChange2%?', \
                        'after3dChangeRatio', 'after5dChangeRatio']
        df_data = df_data.drop(drop_columns, axis=1)
        df_data['after5dRise?'] = pd.factorize(df_data['after5dRise?'])[0]
        # shuffle the data
        df_data = df_data.reindex(np.random.permutation(df_data.index))

        # separate train data and test data
        print("Total number of samples: ", df_data.shape[0])
        print("Total number of features: ", df_data.shape[1])
        num_train = 150        
        print("Number of train data: ", num_train)           
        df_train = df_data.iloc[:num_train,:]
        df_test = df_data.iloc[num_train:,:] 
        
        y_all = df_data['after5dRise?'].values
        X_all = df_data.drop(['after5dRise?'], axis=1).values
        
        X_train, y_train = X_all[:num_train], y_all[:num_train]
        X_test, y_test = X_all[num_train:], y_all[num_train:]
        
        # fit with Random Forest Classifier
        rfc = RandomForestClassifier(max_features=5, n_estimators=500)
        rfc.fit(X_train, y_train)
        score = rfc.score(X_test, y_test)
        print("Test score with RF: ", score)
        
        y_pred = rfc.predict(X_test)
        
        # fit with Gradient Boosting Classifier
        gbc = GradientBoostingClassifier()
        gbc.fit(X_train, y_train)
        score = gbc.score(X_test, y_test)
        print("Test score with Gradient Boosting: ", score)
        

if __name__ == '__main__':
    # set start and end datetime of pstocks
    dt_start, dt_end = datetime(1997,1,1), datetime(2016,2,19)
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create an analysis class
    analysis = RFandGBDTforCstAnalysis('Predict stock price with Random Forest (RF) and GBDT')
    # number of extra daily data for computation (ahead of start datatime)
    n_ahead = 80
    # ask agares
    settings = {'pstocks': pstocks, 'analysis': analysis, 'dt_start': dt_start, 'dt_end': dt_end,
                'n_ahead': n_ahead}
    ask_agares(settings)




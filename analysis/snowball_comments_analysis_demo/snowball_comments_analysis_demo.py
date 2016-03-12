# @file Snowball_comments_analysis_demo.py
# @brief analysis the topics at certain time in the Snowball website

import ipdb
import numpy as np
import pandas as pd
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
from agares.util.handle_Chinese import contain_Chinese
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF, LatentDirichletAllocation


class SnowballCommentsAnalysis(Analysis):
    """ 
    Extract primary topics at certain date from the Snowball website.
    Use NMF and LDA algorithm.
    """
    def __init__(self, name, dt_start, dt_end):
        super(SnowballCommentsAnalysis, self).__init__(name)
        # start date
        self.dt_start = dt_start
        # end date
        self.dt_end = dt_end
        
    def set_jieba(self):
        """
        Suggest frequency to jieba
        """
        for line in open('adjust_words').readlines():
            word = line.strip()
            jieba.suggest_freq(word, True) 
    
    def drop_useless_word(self, words):
        """
        Drop useless word such as stopword and non-Chinese character  
        """
        clean_words = ""
        for word in words:
            if word in self.stopwords:
                continue
            if not contain_Chinese(word):
                continue
            clean_words += " "
            clean_words += word
        return clean_words.strip()     
        
    def print_top_words(self, model, feature_names, n_top_words):
        """
        Output function for NNF and LDA model
        """
        for topic_idx, topic in enumerate(model.components_):
            print("Topic #%d:" % topic_idx)
            print(" ".join([feature_names[i] for i in topic.argsort()[:-n_top_words - 1:-1]]))
        print() 
   
    def perform_analysis(self, stocks, szTimeAxis, n_ahead):
        # load Snowball comment data
        from agares.datasource.snowball_cmt_loader import SnowballCmtLoader
        SBLoader = SnowballCmtLoader()
        date = self.dt_start.date()
        df_cmt_list = []
        while date <= self.dt_end.date():
            df_cmt_list.append(SBLoader.load(str(date)))
            date += timedelta(days=1)
        df_cmt = pd.concat(df_cmt_list, ignore_index=True)
        # Chinese text segmentation
        self.set_jieba()
        df_cmt['RawComment'] = df_cmt['RawComment'].map(jieba.cut)
        # drop stopwords
        self.stopwords = [line.strip() for line in open('stopwords').readlines()]
        self.stopwords.append(' ')
        df_cmt['RawComment'] = df_cmt['RawComment'].map(self.drop_useless_word)
        cmt = df_cmt['RawComment'].tolist()
        # construct tfidf matrix
        tfidf_vectorizer = TfidfVectorizer(ngram_range=(1, 3), max_df=0.95, min_df=0.05)
        tfidf = tfidf_vectorizer.fit_transform(cmt)
        
        # Fit the NMF model
        n_topics = 5
        n_top_words = 20
        print("Fitting the NMF model with tf-idf features..")
        t0 = time()
        nmf = NMF(n_components=n_topics, random_state=1, alpha=.1, l1_ratio=.5).fit(tfidf)
        print("done in %0.3fs." % (time() - t0))
        print("\nTopics in NMF model:")
        tfidf_feature_names = tfidf_vectorizer.get_feature_names()
        self.print_top_words(nmf, tfidf_feature_names, n_top_words)
        
        # Fit the LDA model
        print("Fitting LDA models with tf-idf features..")
        lda = LatentDirichletAllocation(n_topics=n_topics, max_iter=10,
                                        learning_method='online', learning_offset=50.,
                                        random_state=0)
        t0 = time()
        lda.fit(tfidf)
        print("done in %0.3fs." % (time() - t0))
        print("\nTopics in LDA model:")
        self.print_top_words(lda, tfidf_feature_names, n_top_words)
        
        # load sz daily candlestick data
        sz = next(iter(stocks))
        cst_Day = stocks[sz].cst['1Day'] 
        # print close price within the timescope
        date = self.dt_start
        print()
        print("The ShangHai stock Index (close index) within the timescope")
        while date <= self.dt_end:
            ts = pd.to_datetime(date)
            try:
                print("Date: {0:s}, Index: {1:.2f}".format(str(date.date()), cst_Day.at[ts, 'close']))
            except KeyError: # sz candlestick data does not exist at this datetime
                print("Date: {0:s}, Index: (market closed)".format(str(date.date())))
            date += timedelta(days=1)


if __name__ == '__main__':
    # set start and end datetime of pstocks
    dt_start, dt_end = datetime(2016,2,16), datetime(2016,2,19)
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create an analysis class
    analysis = SnowballCommentsAnalysis('Snowball Comments Analysis', dt_start, dt_end)
    # number of extra daily data for computation (ahead of start datatime)
    n_ahead = 20
    # ask agares
    settings = {'pstocks': pstocks, 'analysis': analysis, 'dt_start': dt_start, 'dt_end': dt_end,
                'n_ahead': n_ahead}
    ask_agares(settings)




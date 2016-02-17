# @file SnowBall_comments_analysis_demo.py
# @brief analysis the topics at certain time in the SnowBall website

import ipdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from time import time
from datetime import datetime
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


class SnowBallCommentsAnalysis(Analysis):
    """ 
    Extract primary topics at certain date from the SnowBall website.
    Use NMF and LDA algorithm.
    """
    def __init__(self, name, date):
        super(SnowBallCommentsAnalysis, self).__init__(name)
        self.date = date
        
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
        # load SnowBall comment data
        from agares.datasource.SnowBallCmtLoader import SnowBallCmtLoader
        SBLoader = SnowBallCmtLoader()
        df_cmt = SBLoader.load(str(self.date))
        # Chinese text segmentation
        self.set_jieba()
        df_cmt['RawComment'] = df_cmt['RawComment'].map(jieba.cut)
        # drop stopwords
        self.stopwords = [line.strip() for line in open('stopwords').readlines()]
        self.stopwords.append(' ')
        df_cmt['RawComment'] = df_cmt['RawComment'].map(self.drop_useless_word)
        cmt = df_cmt['RawComment'].tolist()
        # construct tfidf matrix
        tfidf_vectorizer = TfidfVectorizer(max_df=0.95, min_df=2)
        tfidf = tfidf_vectorizer.fit_transform(cmt)
        
        # Fit the NMF model
        n_topics = 10
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


if __name__ == '__main__':
    # list of candlestick data files, each item represents a period data of a interested stock
    # pstocks could contain multiple stock of multiple type of period
    pstocks = ['000001.sz-1Day']
    # create an analysis class
    analysis = SnowBallCommentsAnalysis('SnowBall Comments Analysis', '2016-02-16')
    # set start and end datetime of pstocks
    dt_start, dt_end = datetime(2015,12,1), datetime(2016,1,26)
    # number of extra daily data for computation (ahead of start datatime)
    n_ahead = 30

    settings = {'pstocks': pstocks, 'analysis': analysis, 'dt_start': dt_start, 'dt_end': dt_end,
                'n_ahead': n_ahead}
    ask_agares(settings)




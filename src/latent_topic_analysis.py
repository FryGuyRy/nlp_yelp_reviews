import numpy as np
import pandas as pd
import textacy
import spacy
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import pyLDAvis
import pyLDAvis.sklearn
import restaurants_yelp
from sqlalchemy import create_engine
import psycopg2


#Part 1 retriving reviews from pkl df
def load_pickle(pkl):
    '''
    DESC: Load a pickled pandas DataFrame
    --Input--
        pkl: filepath of pkl file
    ----------------------------------
    --Output--
        Returns pandas dataframe
    '''
    return pd.read_pickle(pkl)

def business_reviews(df, colname, business_id):
    '''
    DESC: Retrive pandas DataFrame containing information for a specified business
    --Input--
        df: pandas dataframe
        colname: (str) column name where business_id/id is located
        business_id: (str) id for business of interest
    ----------------------------------
    --Output--
        Returns pandas DataFrame containing data_review information for a specified business
    '''
    return df[(df[colname] == business_id)]

def to_text(filepath, lst):
    with open(filepath, mode='wt', encoding='utf-8') as f:
        f.write('笑\n'.join(lst))
    return

def connect_psql(df, engine):
    df.to_sql('yelp_restaurant_reviews', con=engine, if_exists='append', index=False)

class NlpTopicAnalysis(object):
    """
    DESC: Takes a pandas DataFrame and allow nlp processing using textacy
    --Input--
        df: pandas dataframe
        textcol: (str) name of column in pandas DataFrame where text are located
        labelcol: (str) name of column in pandas DataFrame where labels are located
    """
    def __init__(self, df=None, textcol=None, labelcol=None, labelcol2=None, text=[]):
        self.spacy = spacy.load('en')
        self.df = df
        self.textcol = textcol
        self.labelcol = labelcol
        self.labelcol2 = labelcol2
        self.vectorizer = None
        self.corpus = None
        self.model = None
        self.text = text
        self.label = []
        self.label2=[]
        self.tfidf = None
        self.topic_matrix = None
        self.latent_topics_top_terms = {}
        self.terms_list = []
        self.topic_w_weights = {}
        self.ldavis = None
        self.tokens = []
        self.token_vectors = None
        self.doc_vectors = None

    def _get_reviews_and_label(self):
        '''
        DESC: Retrive reviews & labels from a column in a pandas DataFrame and append reviews & labels to a list
        ----------------------------------
        --Output--
            Returns 2 lists of items and labels in column of a pandas DataFrame
        '''
        for i in range(self.df.shape[0]):
            self.text.append(self.df[self.textcol].iloc[i])
            if self.labelcol:
                self.label.append(self.df[self.labelcol].iloc[i])
            if self.labelcol2:
                self.label2.append(self.df[self.labelcol2].iloc[i])
        return


    #Part 2 Saving textacy corpus as compressed file
    def process_text(self, filepath=None, filename=None, compression=None):
        '''
        DESC: Tokenizes and processes pandas DataFrame using textacy. If filepath: saves corpus as pickle to filepath.
        --Input--
            filepath: (str) path to directory where textacy corpus will be saved
            filename: (str) name of pickled textacy corpus
            compression: (str) compression of metadata json ('gzip', 'bz2', 'lzma' or None)
        ----------------------------------
        --Output--
            Returns textacy corpus object, if filepath: saves textacy corpus as pickle
        '''
        if len(self.text) == 0:
            self._get_reviews_and_label()
        self.corpus = textacy.Corpus('en')
        self.corpus.add_texts(texts=self.text, batch_size=1000, n_threads=-1)
        if filepath:
            self.corpus.save(filepath, filename, compression)
            print('Saved textacy corpus to filepath.')
        return



    #Part 3 loading textacy corpus from compressed file
    def load_corpus(self, filepath, filename, compression=None):
        '''
        DESC: Loads pickled corpus of textacy/spacy docs
        --Input--
            filepath: (str) path to directory where textacy corpus is located
            filename: (str) name of pickled textacy corpus
            compression: (str) compression of pickled textacy corpus (gzip, 'bz2', 'lzma' or None)
        ----------------------------------
        --Output--
            Returns textacy corpus object
        '''
        self.corpus = textacy.Corpus.load(filepath, filename, compression)
        return


    # Part4 Vectorizing textacy corpus
    def vectorize(self, weighting='tf', min_df=0.1, max_df=0.95, max_n_terms=100000, exclude_pos=['PUNCT','SPACE']):
        '''
        DESC: Creates tf/tfidf/binary matrix of textacy corpus.
            weighting = (str) tf, tfidf, bindary
            min_df = (float/int) exclude terms that appear in less than precentage/number of documents
            max_df = (float/int) exclude terms that appear in more than precentage/number of documents
            max_n_terms = (int) max terms (features) to include in matrix
            exclude_pos = (lst of strs) list of POS tags to remove from vocabulary when creating matrix
        --Output--
            Returns creates tf/tfidf/binary matrix of textacy corpus.
        '''
        for doc in self.corpus:
            self.terms_list.append(list(doc.to_terms_list(n_grams=1, named_entities=True, \
                                                normalize='lemma', as_strings=True, \
                                                filter_stops=True, filter_punct=True, exclude_pos=exclude_pos)))
        self.vectorizer = textacy.Vectorizer(weighting=weighting, normalize=True, \
                                            smooth_idf=True, min_df=min_df, max_df=max_df, max_n_terms=max_n_terms)
        self.tfidf = self.vectorizer.fit_transform(self.terms_list)
        return self.tfidf

    def word2vec(self):
        doc_vects = []
        toks_vects = []
        for ind, doc in enumerate(self.corpus):
            print('going through doc {}...'.format(ind))
            doc_vects.append(doc.spacy_doc.vector)
            # for token in doc.spacy_doc:
            #     if token.orth_ not in self.tokens:
            #         toks_vects.append(token.vector)
            #         self.tokens.append(token.orth_)
        print('creating arrays')
        print(len(doc_vects))
        self.doc_vectors = np.array(doc_vects)
        # print(len(toks_vects))
        # self.token_vectors = np.array(toks_vects)
        print('Done.')


    #Part 2
    def topic_analysis(self, n_topics=10, model_type='lda', n_terms=50, n_highlighted_topics=5, plot=False, save=False, kwargs=None):
        '''
        DESC: Latent topic modeling of tf/tfidf/binary matrix. If plot, generates termite plot of latent topics.
        for corpus on n topics
        --Input--
            n_topics: (int) number of latent topics
            model_type: (str) 'nmf','lsa','lda' or sklearn.decomposition.<model>
            n_terms: (int) number of key terms ploted in termite plot (y-axis)
            n_highlighted_topics: (int) number of highlighted key topics sorted by importance, max highlighted topics is 6
            plot = (bool) if True will create a terminte plot of latent topics
            save = (str) filename to save plot
            kwargs = (dic) takes hyperparameters --> see sklearn.decomposition.<model>
        ----------------------------------
        --Output--
            Creates topic_matrix of num_docs X n_topics dimensions, topic weights/importance for each topic, and termite plot of key terms to latent topics
        '''
        if n_highlighted_topics > 6:
            print('Value Error: n_highlighted_topics must be =< 5')
            return
        highlighting = {}
        self.model = textacy.TopicModel(model_type, n_topics=n_topics, kwargs=kwargs)
        self.model.fit(self.tfidf)
        self.topic_matrix = self.model.transform(self.tfidf)
        for topic_idx, top_terms in self.model.top_topic_terms(self.vectorizer.feature_names, topics=range(n_topics), weights=False):
            self.latent_topics_top_terms[topic_idx] = top_terms
            # print('Topic {}: {}' .format(topic_idx, top_terms))
        for topic, weight in enumerate(self.model.topic_weights(self.topic_matrix)):
            self.topic_w_weights[topic] = weight
            highlighting[weight] = topic
            # print('Topic {} has weight: {}' .format(topic, weight))

        sort_weights = sorted(highlighting.keys())[::-1]
        highlight = [highlighting[i] for i in sort_weights[:n_highlighted_topics]]
        self.model.termite_plot(self.tfidf, \
                                self.vectorizer.feature_names, \
                                topics=-1,  \
                                n_terms=n_terms, \
                                highlight_topics=highlight,col_labels=['Topic 1','Topic 2','Topic 3','Topic 4','Topic 5','Topic 6','Topic 7','Topic 8','Topic 9'])
        plt.tight_layout()
        print('plotting...')
        if save:
            plt.savefig(save)
        if plot:
            plt.show()
        return


    def lda_vis(self, n_words=30):
        '''
        DESC: Creates pyLDAvis figure. Requires LDA topic_analysis model
        --Input--
            n_words = number of words to display in the barcharts of figure
        ----------------------------------
        --Output--
            Returns pyLDAvis figure in html browser
        '''
        doc_lengths = [len(doc) for doc in self.corpus]
        vocab_lst = self.vectorizer.feature_names
        term_freq = textacy.vsm.get_doc_freqs(self.tfidf, normalized=False)
        topic_terms_tups = list(self.model.top_topic_terms(self.vectorizer.feature_names, topics=-1, top_n=len(vocab_lst), weights=True))
        lst = []
        for topic in topic_terms_tups:
            words = []
            for w in topic[1]:
                words.append(w)
            lst.append(words)
            topic_weight = []
            for topic in lst:
                weights = []
                for word in vocab_lst:
                    for we in topic:
                        if word == we[0]:
                            weights.append(we[1])
                topic_weight.append(weights)
        topic_term = np.array(topic_weight)
        self.ldavis = pyLDAvis.prepare(topic_term, \
                                        self.topic_matrix, \
                                        doc_lengths, \
                                        vocab_lst, \
                                        term_freq, \
                                        R=n_words, \
                                        mds='mmds', \
                                        sort_topics=False)
        pyLDAvis.save_html(self.ldavis, 'pyLDAvis_most_reviewed')
        print('plotting...')
        # pyLDAvis.show(self.ldavis)

if __name__ == '__main__':
    print('loaded NlpTopicAnalysis')
    #load pickled dfs
    print('loading reviews pkl...')
    data_reviews = load_pickle('/Users/gmgtex/Desktop/Galvanize/Immersive/capstone/pkl_data/yelp_reviews.pkl')
    # print('loading tips pkl...')
    # data_tips = load_pickle('/Users/gmgtex/Desktop/Galvanize/Immersive/capstone/pkl_data/yelp_tips.pkl')
    print('loading business pkl...')
    data_business = load_pickle('/Users/gmgtex/Desktop/Galvanize/Immersive/capstone/pkl_data/yelp_business.pkl')
    # print('loading user pkl...')
    # data_user = load_pickle('/Users/gmgtex/Desktop/Galvanize/Immersive/capstone/pkl_data/yelp_user.pkl')
    # print('loading checkin pkl...')
    # data_checkin = load_pickle('/Users/gmgtex/Desktop/Galvanize/Immersive/capstone/pkl_data/yelp_checkin.pkl')
    print('Done.')

    ''' most rated business latent topic analysis'''
    # business_id with most reviews 4JNXUYY8wbaaDmk3BPzlWw
    print('collecting reviews of business_id: 4JNXUYY8wbaaDmk3BPzlWw...')
    reviews_4JNXUYY8wbaaDmk3BPzlWw_df = business_reviews(data_reviews, 'business_id', '4JNXUYY8wbaaDmk3BPzlWw')
    print(type(reviews_4JNXUYY8wbaaDmk3BPzlWw_df))
    print('Done.')

    nlp = NlpTopicAnalysis(reviews_4JNXUYY8wbaaDmk3BPzlWw_df, 'text', 'stars')
    nlp = NlpTopicAnalysis()
    nlp.load_corpus(filepath='/Users/gmgtex/Desktop/Galvanize/Immersive/capstone/pkl_data', \
                    filename='corpus_4JNXUYY8wbaaDmk3BPzlWw', \
                    compression=None)
    print(nlp.corpus)
    nlp.vectorize()
    nlp.topic_analysis(n_topics=9, model_type='lda', n_terms=25, n_highlighted_topics=5, plot=True, save='termite_plot_4JNXUYY8wbaaDmk3BPzlWw_lda')
    # nlp.lda_vis()
    print('Done.')

    ''' Getting restaurants text and labels'''
    # print('unpacking attributes...')
    # data_business_unpacked = restaurants_yelp.unpack(data_business, 'attributes')
    # print('Done.')
    # print('merging dfs & finding restaurants...')
    # merged_df = data_reviews.merge(data_business_unpacked, on='business_id', how='left', suffixes=['rev', 'bus'], sort=False, indicator=True)
    # keywords = ['Restaurants']
    # restaurant_df = restaurants_yelp.get_category(df=merged_df,keywords=keywords)
    # restaurant_df.reset_index(inplace=True)
    # print('Done.')
    # print('creating rest_text_target df...')
    # rest_text_target = restaurant_df[['text', 'starsrev', 'RestaurantsPriceRange2']]
    # rest_text_target.dropna(inplace=True)
    # rest_text_target['target'] = rest_text_target['starsrev'].map(str) + '-' + rest_text_target['RestaurantsPriceRange2'].map(str)
    # rest_text_target.drop(labels=['starsrev','RestaurantsPriceRange2'], inplace=True, axis=1)
    # print('Done.')
    # print('pickling df...')
    # rest_text_target.to_pickle("/Users/gmgtex/Desktop/Galvanize/immersive/capstone/pkl_data/rest_text_target_df.pkl")
    # print('Done.')

    '''latent topic analysis resturants df'''
    # print('loading rest_text_target_w_ids_df...')
    # df = load_pickle("../pkl_data/rest_text_target_W_ids_df.pkl")
    # df = df.sort_values(by='review_count', axis=0, ascending=False)
    # rest_ids = set(rest_id for rest_id in df['business_id'])
    # print('Done.')
    #
    # count = 0
    # already_processed = ['Dx5P2QMpxDS6gIXguhAecg', 'PS5ghm09F2km76m4sQNJAw']
    # for i in rest_ids:
    #     if i not in already_processed:
    #         reviews_i = business_reviews(df, 'business_id', i)
    #         engine = create_engine('postgresql+psycopg2://postgres@localhost:5432/yelp_data')
    #         connect_psql(reviews_i, engine)
    #         print('processing_' + i)
    #         nlp = NlpTopicAnalysis(df=reviews_i, textcol='text', labelcol='target', labelcol2='usefulness')
    #
    #         print('processing review...' + i)
    #         nlp.process_text(filepath='pkl_corps', \
    #                                 filename='cor'+i, \
    #                                 compression='gzip')
    #         to_text('txt_files/text_'+i+'.txt', list(nlp.text))
    #         to_text('txt_label_files/label_'+i+'.txt', list(nlp.label))
    #         to_text('txt_label2_files/label_'+i+'.txt', list(nlp.label2))
    #         tf = nlp.vectorize()
    #         np.savez('tf_vec/'+i, tf)
    #         nlp.word2vec()
    #         np.savez('doc2vec/'+i, nlp.doc_vectors)
    #         if len(nlp.text) > 100:
    #             nlp.topic_analysis(n_topics=7, model_type='lda', n_terms=50, n_highlighted_topics=3, plot=False, save='termiteplot_lda' + i)
    #             plt.close('all')
    #             nlp.lda_vis()
    #         already_processed.append(i)
    #         count +=1

    '''resturants_w_ids df...'''

    ''' NLP subset'''
    # print('loading rest_text_target_w_ids_df...')
    # rest_text_target_w_ids_df = load_pickle("../pkl_data/rest_text_target_w_ids_df.pkl")
    # print('Done.')
    # g500 = rest_text_target_w_ids_df[rest_text_target_w_ids_df['review_count'] >=500]
    # print(g500.info())
    # nlp_g500 = NlpTopicAnalysis(df=g500, textcol='text', labelcol='target')
    # print('processing restaurants_dfs...')
    # nlp_g500.process_text(filepath='../pkl_data', \
    #                         filename='g500_corpus', \
    #                         compression='gzip')
    # print('writing to text file...')
    # nlp_g500.to_text('../pkl_data/g500_text.txt', nlp_g500.text)
    # nlp_g500.to_text('/../pkl_data/g500_targets.txt', nlp_g500.labels)
    # print('Done.')

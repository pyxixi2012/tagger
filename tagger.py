#!/usr/bin/env python

'''
module for extracting tags from text documents


Usage:


import tagger

weights = pickle.load(open('data/dict.pkl', 'r'))
# or your own dictionary
# if using the standard Rater class, this should be a
# defaultdict(lambda: 1.0) of IDF weights, normalized in the interval [0,1]
 
myreader = tagger.Reader() # or your own reader class
mystemmer = tagger.Stemmer() # or your own stemmer class
myrater = tagger.Rater(weights) # or your own... (you got the idea)

mytagger = Tagger(myreader, mystemmer, myrater)

best_3_tags = mytagger(text_string, 3)


Remember loading a huge dictionary takes quite some time, so try to reuse the
same Tagger object for documents of the same type and language.


Running the tagger as a script:

./tagger.py document_to_tag.txt

'''

import collections
import operator
import re


class Tag:
    '''
    General class for tags (small units of text)
    '''
    
    def __init__(self, string, stem=None, rating=1.0, terminal=False):
        '''

        Arguments:

        string    --    the actual representation of the tag
        stem      --    the internal (usually stemmed) representation;
                        tags with the same stem are regarded as equal
        rating    --    a measure of the relevance in the interval [0,1]
        terminal  --    set to True if the tag is at the end of a phrase
                        (or anyway it cannot be logically merged to the
                        following one)

        Returns: a new Tag object
        '''
            
        self.string  = string
        self.stem = stem or string
        self.rating = rating
        self.terminal = terminal

    def __eq__(self, other):
        return self.stem == other.stem

    def __repr__(self):
        return self.string

    def __lt__(self, other):
        return self.rating > other.rating

    def __hash__(self):
        return hash(self.stem)


class MultiTag(Tag):
    '''
    Class for aggregates of tags (usually next to each other in the document)
    '''

    def __init__(self, tail, head=None):
        '''

        Arguments:

        tail    --    the Tag object to add to the first part (head)
        head    --    the (eventually absent) MultiTag to be extended

        Returns: a new MultiTag object
        '''
        
        if not head:
            Tag.__init__(self, tail.string, tail.stem, tail.rating)
            self.size = 1
        else:
            self.string = ' '.join([head.string, tail.string])
            self.stem = ' '.join([head.stem, tail.stem])
            self.rating = head.rating * tail.rating
            self.size = head.size + 1

        self.terminal = tail.terminal
            
    def __lt__(self, other):
        # the measure for multitags is the geometric mean of its unit subtags
        return self.rating ** (1.0 / self.size) > \
            other.rating ** (1.0 / other.size)
        
            
class Reader:
    '''
    Class for parsing a string of text to obtain tags

    (it just turns the string to lowercase and splits it according to
    whitespaces and punctuation; different rules and formats could be used,
    e.g. a good HTML-stripping facility would be handy)
    '''

    def __call__(self, text):
        '''

        Arguments:

        text    --    the string of text to be tagged

        Returns: a list of tags respecting the order in the text
        '''

        text = text.lower()
        delimiters = '\.,:;!?"\(\)\[\]\{\}\n\t\^~'
        phrases = re.split('[' + delimiters + ']+', text.strip(delimiters))

        tags = []

        for p in phrases:
            words = p.split()
            if len(words) > 0:
                for w in words[:-1]:
                    tags.append(Tag(w))
                tags.append(Tag(words[-1], terminal=True))

        return tags
    
class Stemmer:
    '''
    Class for extracting the stem of a word
    
    (uses a simple open-source implementation of the Porter algorithm;
    this can be improved a lot, so experimenting with different ones is
    advisable)
    '''
    
    def __call__(self, tag):
        '''

        Arguments:

        tag    --    the tag to be stemmed

        Returns: the stemmed tag
        '''

        import porter

        tag.stem = porter.stem(tag.string)

        return tag
        

class Rater:
    '''
    Class for estimating the relevance of tags

    (uses TF-IDF weight and geometric mean for multitags; a quite trivial
    heuristic tries to discard redundant tags)
    '''

    def __init__(self, weights, multitag_size=3):
        '''
        Constructor for class Rater

        Arguments:

        weights          --    a dictionary of IDF weights normalized in the
                               interval [0,1]; preferably of type:
                                   defaultdict(lambda: 1.0)
        multitag_size    --    maximum size of tags formed by multiple unit
                               tags
        '''
        
        self.weights = weights
        self.multitag_size = multitag_size
    
    def __call__(self, tags):
        '''

        Arguments:

        tags    --    a list of (preferably stemmed) tags

        Returns: a list of unique (multi)tags sorted by relevance
        '''

        term_count = collections.Counter(tags)
        
        for t in tags:
            t.rating = float(term_count[t]) / len(tags) * \
                weights[t.stem]

        multitags = []
        for i in range(len(tags)):
            t = MultiTag(tags[i])
            multitags.append(t)
            for j in range(1, self.multitag_size):
                if i + j < len(tags) and not t.terminal:
                    t = MultiTag(tags[i + j], t)
                    multitags.append(t)

        term_count = collections.Counter(multitags)

        unique_tags = set(multitags)
        for t in multitags:
            # purge one-character tags
            if len(t.string) < 2:
                unique_tags.discard(t)
                continue
            # remove redundant tags
            words = t.stem.split()
            for i in range(len(words)):
                for j in range(1, len(words)):
                    subtag = Tag(' '.join(words[i:i + j]))
                    relative_freq = float(term_count[t]) / term_count[subtag]
                    if relative_freq >= 0.5 and t.rating > 0.0:
                        unique_tags.discard(subtag)
                    else:
                        unique_tags.discard(t)
                        
        return sorted(unique_tags)
    
    
class Tagger:
    '''
    Master class for tagging text documents

    (this is a simple interface that should allow convenient experimentation
    by using different classes as building blocks)
    '''

    def __init__(self, reader, stemmer, rater):
        '''

        Arguments:

        reader    --    a callable object with the same interface as Reader
        stemmer   --    a callable object with the same interface as Stemmer
        rater     --    a callable object with the same interface as Rater
        '''
        
        self.reader = reader
        self.stemmer = stemmer
        self.rater = rater

    def __call__(self, text, tags_number=5):
        '''

        Arguments:

        text           --    the string of text to be tagged
        tags_number    --    number of best tags to be returned

        Returns: a list of (hopefully) relevant tags
        
        ''' 

        tags = self.reader(text)
        tags = map(self.stemmer, tags)
        tags = self.rater(tags)
        
        return tags[:tags_number]

if __name__ == '__main__':

    import pickle
    import sys
    
    weights = pickle.load(open('data/dict.pkl', 'r'))
    
    tagger = Tagger(Reader(), Stemmer(), Rater(weights))

    with open(sys.argv[1], 'r') as file:
        print(tagger(file.read(), 5))
          
import random
random.seed() # use current time to seed

class Extractor():
    def __init__(self, path=''):
        self.empty = True # state
        self.path = path # location of poem.txt
        # poem data:
        self.pure_text = ''
        # text collections
        self.poem = [] # text grouped by stanzas
        self.line_list = [] # includes blank lines (except last)
        self.word_list = [] # all words
        # totals
        self.nstanzas = 0
        self.nlines = 0
        self.nwords = 0
        # load poem
        if self.path:
            self.load(self.path)

    # Load a new poem into this object
    def load(self, path):        
        # clear previous data before loading
        if not self.empty:
            self.__init__()

        self.path = path # save path to current poem

        # open file
        with open(path, 'r', encoding='utf-8') as file:
            # extract contents
            plain_text = file.read().strip()

            # group by stanza
            ## each stanza must end with a blank line to be read
            current_verse = ''
            for line in plain_text.splitlines():
                current_verse += line
                # blank line indicates stanza finished (must end with blank line)
                if not line:
                    if not current_verse: # multiple blank lines in a row
                        continue
                    current_verse = current_verse[:-1] # remove last newline (verse is finished)
                    self.poem.append(current_verse)
                    self.nstanzas += 1
                    current_verse = '' # prepare next verse
                else:
                    current_verse += '\n' # prepare for next line

            # group by line
            self.line_list = plain_text.splitlines()
            self.nlines = len(self.line_list)

            # group by word
            self.word_list = plain_text.split() # all words
            self.nwords = len(self.word_list)
            # isolate words (remove punctuation)
            for i in range(self.nwords):
                # only keep letters that are in the alphabet for each word
                self.word_list[i] = ''.join(filter(lambda s : s.isalpha(), self.word_list[i]))
            
            # success
            self.empty = False

    # Base Function
    def get_element(self,n,collection,return_none=True):
        # returns the nth elemnt from a poem grouping
        # 0 - indicates a random element
        # return_none - determines if a random element can be blank

        # Poem must be loaded to use
        if self.empty:
            raise TypeError('No poem is loaded in the extractor')

        # Search grouping:
        size = len(collection)
        default = ''

        # Invalid number
        if not isinstance(n,int):
            return default
        # Find element
        elif n > 0 and n <= size:
            return collection[n-1]
        # Random element
        elif n == 0:
            if return_none:
                return random.choice(collection)
            else:
                # no empty elements
                return random.choice([item for item in collection if item])
        # Out of bounds
        else:
            return default

    # Utility Functions:
    def get_verse(self,n=0):
        ''' returns the nth stanza from the poem

            0 - indicates a random stanza
        '''
        return self.get_element(n,self.poem)

    def get_line(self,n=0):
        ''' returns the nth line from the poem

            0 - indicates a random line (that exists)
        '''
        return self.get_element(n,self.line_list,False)

    def get_word(self,n=0):
        ''' returns the nth word from the poem

            0 - indicates a random word
        '''
        return self.get_element(n,self.word_list)


# Demo
if __name__ == '__main__':
    path = input('Poem text file (path): ')
    print()
    new_poem = Extractor(path)
    print('Stanza 1:')
    x = new_poem.get_verse(1)
    if x:
        print(x)
    else:
        print('(blank)')
    print()
    print('Line 1:')
    x = new_poem.get_line(1)
    if x:
        print(x)
    else:
        print('(blank)')
    print()
    print('Word 1:')
    x = new_poem.get_word(1)
    if x:
        print(x)
    else:
        print('(blank)')
    print()
    print('End> ')

import curses
import pyperclip
import math
color_num = 1 # global

# Main Screen
class Screen():
    # static class variables
    UP = -1
    DOWN = 1
    BOX_HEIGHT = 3
    
    # ATTRIBUTES (property,color)
    # Property List:
    # 0 - none
    # 1 - temporary (next item erases this one)
    # 2 - dynamic (most recent is highlighted)
    # 3 - removable (can be cleared separately)

    # Color List:
    # 0 - standard
    # 1 - highlighted text
    # 2 - adaptive (standard -> highlight)
    # 3 - critical (caution msg)
    # 4 - alert (warning msg)
    # 5 - success (approval msg)
    # 6 - dim

    # presets (can modify):
    ATR_STANDARD = [0,0] # standard
    ATR_HIGHLIGHT = [0,1] # highlight
    ATR_NOTICE = [1,1] # highlight (temp)
    ATR_SCAFFOLDING = [3,1] # highlight (removable)
    ATR_DYNAMIC = [0,2] # standard (dynamic) [default]
    ATR_CRITICAL = [0,3] # critical
    ATR_CAUTION = [1,3] # critical (temp)
    ATR_ALERT = [0,4] # alert
    ATR_WARNING = [1,4] # alert (temp)
    ATR_SUCCESS = [0,5] # success
    ATR_APPROVE = [1,5] # success (temp)
    ATR_DIM = [0,6] # dim
    ATR_GHOST = [1,6] # dim (temp)
    ATR_DEBUG = [0,7] # debug
    # -- empty --
    ATR_CUSTOM_1 = [0,8]
    ATR_CUSTOM_2 = [0,9]

    def __init__(self):
        # setup environment
        self.window = curses.initscr() # MAIN screen
        self.window.keypad(1) # recognize special keys (shift, arrows)

        self.height, self.width = self.window.getmaxyx() # screen boundaries

        curses.noecho()
        curses.cbreak() # react to keys instantly
        #curses.curs_set(False) # hide cursor

        # setup colors
        if curses.has_colors:
            curses.start_color()
            # general colors
            # -- standard
            self.white = make_color(curses.COLOR_WHITE,curses.COLOR_BLACK)
            self.red = make_color(curses.COLOR_RED,curses.COLOR_BLACK)
            self.green = make_color(curses.COLOR_GREEN,curses.COLOR_BLACK)
            self.blue = make_color(curses.COLOR_BLUE,curses.COLOR_BLACK)
            self.yellow = make_color(curses.COLOR_YELLOW,curses.COLOR_BLACK)
            self.magenta = make_color(curses.COLOR_MAGENTA,curses.COLOR_BLACK)
            self.cyan = make_color(curses.COLOR_CYAN,curses.COLOR_BLACK)
            # -- added
            self.grey = make_color(8,curses.COLOR_BLACK)
            self.purple = make_color(62,curses.COLOR_BLACK)
            self.pink = make_color(212,curses.COLOR_BLACK)
            # functional colors [customizable]
            self.c_standard = self.white
            self.c_highlight = self.cyan
            self.c_dim = self.grey
            self.c_success = self.green
            self.c_critical = self.yellow # use 227?
            self.c_alert = self.red | curses.A_BOLD
            self.c_debug = self.pink
            # extra colors to assign
            self.c_custom_1 = self.white
            self.c_custom_2 = self.white

        # input box
        self.default_prompt = 'Type Here: '
        self.rest_prompt = 'Press any key to continue . . . '
        y = self.height - self.BOX_HEIGHT
        x = 0
        pos = (y,x) # index values (opposed to height/width)
        self.typebox = InputBox(self.BOX_HEIGHT,self.width,self.height,pos,self.default_prompt,None)

        # basic screen utilities
        # defaults
        self.locked = False # cannot close window
        self.locked_box = False # cannot toggle typing
        self.force_shutdown = False # end run after next blocking call completes
        self.show_scrollbar = True
        self.show_cursor = True
        self.show_box = True
        self.can_type = True # able to write in box
        self.show_color = True
        self.output_function = 1 # the action that occurs when input is entered, param = msg -- 1 is default function (add to screen)

        self.x_margin = self.width - 4 # maximum columns occupied before text is wrapped
        self.min_wrapsize = 32 # smallest amount of characters that can cause text to be wrapped to the next line

        # original copies of text with their attributes
        self.item_record = [] # un-wrapped lines of text as they were input to the screen
        self.attribute_record = []

        self.items = [] # list of on-screen text
        self.attribute_map = [] # maps pairs of values to items - (property,color)

        self.history = [] # archive previously entered items
        self.history_selector = -1 # cycle through the item history
        self.frozen_history = True # next UP keypress will bring up current selection
        self.history_length = 5 # max history memory

        self.current = 0 # index of top most item on screen
        self.max_lines = self.height - self.BOX_HEIGHT - 1 # maximum visible line count (3 up from the bottom of screen)

    # change the size of the imaginary window that displays items
    def update_render_frame(self):
        # maximum visible line count (x up from the bottom of screen), x = height of typebox
        if self.show_box:
            self.max_lines = self.height - self.BOX_HEIGHT - self.typebox.extra_lines - 1 # leave 1 empty row between screen and box
        else: # typebox is not displayed
            self.max_lines = self.height
        # cap max lines at 0 (typebox is larger than screen) as a precaution
        if self.max_lines < 0:
            self.max_lines = 0
        # update frame position (prevent overflow)
        self.check_top_overflow()
        self.check_bottom_overflow()

    def alarm(self):
        curses.beep()

    def pause(self,show_latest=False,alt_prompt=''):
        # save working data from the typebox (includes prompt)
        temp_string = self.typebox.string
        # display pause window -- switch typebox fields temporarily
        if alt_prompt:
            self.typebox.string = alt_prompt
        else:
            self.typebox.string = self.rest_prompt
        self.display(show_latest)
        self.window.getch() # wait for keypress
        # restore typebox data
        self.typebox.string = temp_string

    def quit(self,show_latest=False): # called when screen is running -- ends screen abruptly and does not save working data or prompt
        self.force_shutdown = True # next keypress will stop the screen from running -- currently getch() is blocking
        # indicate keypress results in termination
        self.typebox.string = ''
        self.typebox.new_prompt(self.rest_prompt) # updates string
        if not self.show_box: # make sure prompt is seen
            self.locked_box = False
            self.toggle_typing()
        self.display(show_latest)

    # disengage curses
    def close(self):
        curses.echo()
        curses.nocbreak()
        self.window.keypad(0)
        curses.endwin() # restore the terminal to its original operating mode

    def refresh_items(self):
        # erase all screen items and their attributes
        self.items = []
        self.attribute_map = []
        # re-add each item to the screen (wrapping as necessary) and update screen attributes
        for new_item, value_pair in zip(self.item_record,self.attribute_record):
            self.add(new_item,attr=value_pair,record=False) # do not save another record of this item

    def resize(self,refresh=True):
        self.height, self.width = self.window.getmaxyx() # screen boundaries
        self.x_margin = self.width - 4 # maximum columns occupied before text is wrapped
        self.update_render_frame() # new number of visible rows
        # resize all items to fit within new screen dimensions -- bottom overflow may occur if on last page and screen is widened
        if refresh:
            self.refresh_items()
        # adjust rendering frame
        self.check_top_overflow()
        self.check_bottom_overflow() # make sure screen isn't scrolled further than last item
        # resize + move input box:
        self.typebox.max_height = self.height # update max size
        # new dimensions
        cols = self.width # length of screen
        self.typebox.update_width(cols) # height is scaled according to width to accommodate content
        # position is shifted so the box is anchored to the bottom of its max hieght

    def update_cursor(self):
        # typebox enabled
        if self.show_box:
            curses.curs_set(self.show_cursor) # show cursor (if enabled)
        # typebox disabled
        else:
            curses.curs_set(False) # always hide cursor

    def toggle_cursor(self):
        self.show_cursor = not self.show_cursor # invert state
        self.update_cursor() # show / hide

    def toggle_typing(self):
        if self.locked_box:
            return
        self.show_box = not self.show_box # invert state
        self.update_cursor() # show / hide
        # move frame -- achor bottom (proiritize last item staying on bottom)
        if not self.show_box: # frame got larger (box went away)
            # scroll up to bring last to the bottom of the frame
            self.current -= (self.BOX_HEIGHT + self.typebox.extra_lines + 1)
        else: # frame got smaller (box came back)
            # scroll down to bring last item above the box
            self.current += (self.BOX_HEIGHT + self.typebox.extra_lines + 1)
        # adjust space for presence/absence of box
        self.update_render_frame() # detects overflow

    def toggle_color(self):
        self.show_color = not self.show_color # toggle screen color on/off
        self.typebox.switch_color(self.show_color) # turn box color on/off

    def run(self, limit=-1): # limit how many times the user can enter before the screen stops running
        uses = 0

        # keep running until interrupted or limit is reached
        while limit == -1 or uses < limit:
            self.display() # update display

            ch = self.window.getch()
            if self.force_shutdown and ch != curses.KEY_RESIZE: # shutdown screen immediately
                # prepare screen for next use
                self.force_shutdown = False
                self.typebox.new_prompt(self.default_prompt)
                return 1
            if ch == curses.KEY_UP:
                self.scroll(self.UP)
            elif ch == curses.KEY_DOWN:
                self.scroll(self.DOWN)
            elif ch == curses.KEY_LEFT:
                self.skip_page(self.UP)
            elif ch == curses.KEY_RIGHT:
                self.skip_page(self.DOWN)
            elif ch == curses.KEY_HOME: # skip to top
                self.current = 0
            elif ch == 10: # ENTER = skip to recent / process input
                if self.show_box:
                    if self.typebox.enter(): # check if typebox has a message
                        message = self.typebox.output # final string is ready for output
                        self.add_history(message) # resets history reel
                        self.process_input(message)
                        self.update_render_frame()
                        uses += 1 # screen has been used another time -- item entered
                self.show_recent() # skip to bottom
            elif ch == curses.KEY_RESIZE:
                self.resize()
            elif ch == 27: # ESCAPE = stop running
                if self.locked:
                    continue
                return 0
            elif ch == 490: # Alt, up
                self.load_history(self.UP)
            elif ch == 491: # Alt, down
                self.load_history(self.DOWN)
            elif ch == 433: # Alt+q
                self.toggle_color()
            elif ch == 420: # Alt+d
                self.toggle_typing()
            elif ch == 424: # Alt+h
                self.toggle_cursor()
            else: # character with a non-specific function 
                if self.show_box and self.can_type:
                    self.typebox.input(ch) 
                    self.update_render_frame() # number of visible rows


    def show_recent(self):
        if len(self.items) > self.max_lines: # at least a screen of items
            self.current = len(self.items) - self.max_lines # fill the screen, so that the last item on screen is the last item in list
        else:
            self.current = 0

    def is_latest(self):
        # find out if the screen is showing recent
        if self.current == len(self.items) - self.max_lines:
            return True
        else:
            return False

    def check_top_overflow(self):
        # top of screen cannot go past first item
        if self.current < 0:
            self.current = 0

    def check_bottom_overflow(self):
        # bottom of screen cannot go further than last item, unless there is not a full screen of items! (handled in show_recent)
        if self.current + self.max_lines > len(self.items): # position of bottom item on screen exceeds the number of items that exist
            self.show_recent() # move back up so bottom is last item

    def scroll(self,direction):
        # Up
        # - the current item (at the top) must not be the first item in the list, otherwise there is no space to move up
        if (direction == self.UP) and (self.current > 0):
            self.current += direction
        # Down
        # - the last item that can POSSIBLY be shown on screen must be less than the last item in the list; there is nothing more to show downwards
        if (direction == self.DOWN) and (self.current + self.max_lines < len(self.items)):
            self.current += direction

    def skip_page(self,direction):
        # Skip a Page
        self.current += (self.max_lines * direction)
        # Up overflow
        self.check_top_overflow()
        # Down overflow
        self.check_bottom_overflow()

    def add_history(self,new_item):
        # short-circuit if history is empty (prevents IndexError)
        # empty history will always add item and reset cycle
        self.frozen_history = True # always freeze history when a new item is added (next up press shows current selection)

        # do not allow the same item to be added consecutively
        if self.history and new_item == self.history[-1]:
            return
        else: # add item to history
            self.history.append(new_item)
            # maintain selection -- becomes earlier in memory (may exceed history length)
            self.history_selector += self.UP

        # restrict size
        if len(self.history) > self.history_length:
            self.history.pop(0) # forget oldest element

        # restart cycle:
        # selector overflow (tracked item no longer in memory)
        if self.history_selector < -len(self.history):
                self.history_selector = -1 # reset
        # entered item differs from current history selection
        elif not self.history or new_item != self.history[self.history_selector]:
            self.history_selector = -1

    def clear_history(self):
        self.history.clear()
        self.history_selector = -1
        self.frozen_history = True

    def load_history(self,d=0):
        # load previously entered item into typebox
        # d: -1 = earlier, +1 = later
        if not self.show_box:
            return

        # move selector
        if self.frozen_history and d == self.UP: # up keypress maintains selection when frozen
            pass # stay on current selection
        else:
            self.history_selector += d

        # restrict bounds
        blocked = True # tried to go past bounds (stay on current record)
        history_size = len(self.history) # number of items in history
        if self.history_selector > -1: # no items newer than this
            self.history_selector = -1
        elif self.history_selector < -history_size: # cannot recall prior to this point
            self.history_selector = -history_size
        else:
            blocked = False # cycled to an existing index
            # freeze is cleared when a valid index is reached -- whether it was used to maintain selection or not
            self.frozen_history = False # only remain frozen when down keypress results in off bounds
            
        # bring up selected item
        if not blocked: # only change string if moving to a NEW record
            previous_item = self.history[self.history_selector]
            self.typebox.change_string(previous_item)

    # defines what happens to data in the typebox after pressing enter -- [CUSTOMIZE] with output_function
    def process_input(self,msg):
        if not self.output_function: # do not process input
            return
        elif self.output_function == 1: # default action
            self.add(msg) # add to screen
            self.typebox.output = '' # clear the output for new data
        else:
            try: # attempt to perform the output action
                self.output_function(msg) # specified function
            except:
                return # do nothing

    def add(self,text='',attr=None,record=True): # add an item to the screen
        # set default attribute
        if not attr:
            attr = self.ATR_DYNAMIC

        # empty text will skip a line (by default)
        # temporarily append an extra char to text so that an additional element will be generated if the text ends with a newline
        text += '!'

        # each newline will be treated as another item (same attr)
        text_list = text.splitlines() # line fragments
        total_lines = len(text_list)

        for i, item in enumerate(text_list):
            # remove extra char
            if i == total_lines - 1:
                item = item[:-1]

            # save a record if this item was added for the first time
            if record:
                self.vanish() # items with the temp property get cleared (not on refresh)
                self.item_record.append(item)
                self.attribute_record.append(attr)

            # Add text to screen-rendering list:
            # wrap text to next line (if necessary)
            length = len(item) # length of input text
            max_length = max(self.x_margin, self.min_wrapsize) # lines cannot have more characters than this (wrap text)
            if length > max_length:
                wrapped_text = [item[:max_length],item[max_length:]] # break the text into appropriately sized lines
                while len(wrapped_text[-1]) > max_length: # repeat until a sequence of correctly sized chunks remain
                    break_text = wrapped_text.pop() # break apart last line further
                    new_chunks = [break_text[:max_length],break_text[max_length:]]
                    wrapped_text.extend(new_chunks) # reattach new lines
                # now add each adjusted string
                for string in wrapped_text:
                    # add each individual chunk of text
                    self.items.append(string)
                    self.attribute_map.append(attr) # all chunks have same attribute
            # not wrapped
            else:
                self.items.append(item) # add the whole item
                self.attribute_map.append(attr)

    # remove items with a specific property
    def clear_marked(self, property):
        attribute_copy = self.attribute_record.copy() # list of all item attributes
        for attr in attribute_copy:
            if attr[0] == property: # marked item
                self.remove_item(self.attribute_record.index(attr)) # remove this item from memory
        if len(attribute_copy) != len(self.attribute_record): # some items have been deleted
            self.refresh_items()

    # erase temporary items
    def vanish(self):
        self.clear_marked(1) # temp property = 1

    # clear removable items
    def scrap(self):
        self.clear_marked(3) # removable property = 3

    # erase item at specific location
    def remove_item(self,index):
        # erase from history
        self.item_record.pop(index)
        self.attribute_record.pop(index)

    # clear all items
    def clear(self):
        # clear history
        self.item_record = []
        self.attribute_record = []
        # clear screen-rendering list
        self.items = []
        self.attribute_map = []
        # refresh display
        self.display(1) # resets current back to 0 (no items)

    def draw_scrollbar(self):
        # Only draw bar if there are more items than can fit on screen
        total_items = len(self.items)
        if total_items > self.max_lines:
            excess = total_items - self.max_lines # off-screen items (min. 1)
            bar_length = self.max_lines - excess 
            if bar_length < 1: # smallest bar indication (1 line)
                bar_length = 1

            # incr = amount of spaces the bar can move / number of items to move past
            # (the last x items will not be passed over as the screen cannot go lower)
            incr = (self.max_lines - bar_length) / excess # how much the bar moves down after passing each item 
            # Positions start from 0 (to max_lines - bar_length)
            top = (self.current * incr) # start of line (top)
            # Top must be an integer.
            # Round up so that only the very first item has top=0
            # However, do not round up to make top=max
            # -----
            # Extreme positions of bar can only be reached when current is at max / min
            # Second last bar space will be covered twice as often as other spaces to accomodate (rounds up AND down to it)
            if top > self.max_lines - bar_length - 1: # second last bar space
                top = math.floor(top) # round down (accounts for floating-point error)
            else:
                top = math.ceil(top) # round up

            # DRAW
            bar_line = '|'
            self.window.vline(top,self.width-2,bar_line,bar_length) # additional 1 space before right side of screen

    def display(self,show_latest=False):
        self.window.erase() # clear contents
        if show_latest: # make sure new items are shown
            self.show_recent()

        # section of list on screen
        top = self.current
        bottom = top + self.max_lines # position of bottom most item on screen (NOT INDEX)
        # if a screen worth of items does not exist, bottom exceeds the item list -- this is OK
        if bottom > len(self.items):
            bottom = len(self.items)

        # if bottom <= top, the render frame does not exist => no items will be drawn
        if bottom > top:
            screen_items = self.items[top:bottom]
            screen_attributes = self.attribute_map[top:bottom]

            # check for most recent item
            last_page = False
            if bottom == len(self.items): # last item on screen is last item in the LIST
                last_page = True

            x = 0 # always start from left of the screen
            n = self.x_margin # do not try to display more characters than can fit on the screen
            for y, item in enumerate(screen_items): # obtain the items and their index on the screen
                if not item: # blank line
                    continue
                # add contents to screen
                try:
                    # color picker:
                    color = None
                    if not self.show_color: # use fallback display
                        raise Exception('Color Off')

                    # Dynamic text (most recent is highlighted) -- property 2 or adaptive color
                    if screen_attributes[y][0] == 2 or screen_attributes[y][1] == self.ATR_DYNAMIC[1]:
                        # index matches the lowest item, and screen on the last page of items => last item in list
                        if last_page and y == len(screen_items) - 1:
                            color = self.c_highlight
                        # adaptive color is standard when not highlighted
                        elif screen_attributes[y][1] == self.ATR_DYNAMIC[1]:
                            color = self.c_standard
                        else: # keep searching for color
                            pass

                    # set color -- not affected by dynamic text
                    if not color:
                        # Highlighted text
                        if screen_attributes[y][1] == self.ATR_HIGHLIGHT[1]:
                            color = self.c_highlight
                        # Success text
                        elif screen_attributes[y][1] == self.ATR_SUCCESS[1]:
                            color = self.c_success
                        # Critical text
                        elif screen_attributes[y][1] == self.ATR_CRITICAL[1]:
                            color = self.c_critical
                        # Alert text
                        elif screen_attributes[y][1] == self.ATR_ALERT[1]:
                            color = self.c_alert
                        # Dim text
                        elif screen_attributes[y][1] == self.ATR_DIM[1]:
                            color = self.c_dim
                        # Debug text
                        elif screen_attributes[y][1] == self.ATR_DEBUG[1]:
                            color = self.c_debug
                        # Custom 1
                        elif screen_attributes[y][1] == self.ATR_CUSTOM_1[1]:
                            color = self.c_debug
                        # Custom 2
                        elif screen_attributes[y][1] == self.ATR_CUSTOM_2[1]:
                            color = self.c_debug
                        # Standard [undefined] 
                        else:
                            color = self.c_standard

                    # draw to screen
                    self.window.addnstr(y, x, item, n, color)

                except: # fallback display
                    self.window.addnstr(y, x, item, n, curses.color_pair(0)) # use default display

            self.draw_scrollbar() # indicate pos of screen relative to total items

        self.window.noutrefresh() # mark MAIN window for refresh
        if self.show_box:
            self.typebox.display() # update the input box window - cursor finishes at the end of message
            if self.show_cursor:
                # move the cursor to the typebox prompt:
                new_y, new_x = self.typebox.window.getyx() # this is the cursor relative to the box
                # get the pos relative to the main window (translate)
                new_y += self.typebox.y
                new_x += self.typebox.x
                self.window.move(new_y,new_x) # moves cursor
        curses.doupdate() # update physical screen


# Input Window
class InputBox():
    def __init__(self,h,w,maxh,pos=(0,0),prompt='',line_limit=None):
        # Window settings
        # pos = (y,x)
        self.y, self.x = pos # relative to main win
        #self.window = curses.newwin(h,w,self.y,self.x)
        self.window = curses.newpad(h,w) # not restricted by display -- abstract window, only portion is rendered to screen
        self.height, self.width = self.window.getmaxyx()
        self.base_height = self.height # initial height
        self.max_height = maxh

        # Box settings
        self.prompt = prompt
        self.prompt_size = len(prompt)
        self.margin = 2 # box bar + space (this is where the prompt starts)
        self.line_length =  self.width - 2*self.margin # number of available chars within one line of the box
        self.extra_lines = 0
        self.offset_y = 0 # how many lines are overflown past the top of the screen
        self.line_limit = line_limit # total lines (extra_lines + 1) cannot exceed this
        self.tabsize = 4 # spaces for indent

        # Output
        self.string = self.prompt # store the current data typed into the box, keep adding chars (includes prompt)
        self.output = '' # store the final string until used by another operation
        self.special_chars = '/\\()[]{}<>:;,.!?|+-=\'"@#$%^&*~_·—– \r\n'
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        numbers = '0123456789'
        self.standard_chars = alphabet.upper() + alphabet + numbers
        self.available_chars = self.standard_chars + self.special_chars

        # Color -- defaults
        self.color = curses.color_pair(0) # standard display
        self.color_on = True

    # calculate how many extra lines are required to fit the current string
    def update_lines(self):
        # calculate size of string, replaces newlines with whitespaces to fill out box dimensions
        string_size = len(self.skip_lines())
        old_lines = self.extra_lines
        # box must be able to contain 1 more char than the string holds, to include cursor
        # extra characters (not in first line) / characters that fit in one line
        self.extra_lines = math.ceil((string_size - self.line_length + 1) / self.line_length)
        # apply ceiling
        self.restrict_box()
        # expand / collapse box
        if self.extra_lines != old_lines: # changed size
            self.shift()

    # update available space within the box
    def update_line_length(self):
        self.line_length = self.width - 2*self.margin
        self.update_lines() # length changed

    # place window relative to main screen (no restrictions)
    def set_pos(self,pos=(0,0)): # pos (y,x)
        y, x = pos
        self.y = y
        self.x = x

    # anchor window to the bottom of its max height
    def update_pos(self):
        # lowest pos on-screen = max_height - 1
        self.y = self.max_height - self.height

    # add or remove ROWS to contain text (only affects height)
    def shift(self):
        self.height = self.base_height + self.extra_lines # recalculate height

        # restrict bounds -- offset box to remain on-screen (imaginary box moves up)
        if self.height > self.max_height:
            overflow = self.height - self.max_height
            self.height = self.max_height # cap height at frame size
            self.offset_y = overflow
        else:
            self.offset_y = 0 # entire box is real (fits on screen)
            
        # resize window
        self.window.resize(self.height,self.width)
        # set new position relative to screen
        self.update_pos()

    def update_width(self,cols):
        self.width = cols
        self.update_line_length() # more/less characters can fit on one line
        self.shift() # rescale box height to fit lines -- resizes window

    def restrict_box(self):
        # if max lines were reached, prevent more text from being added
        if self.line_limit and self.extra_lines + 1 > self.line_limit:
            self.extra_lines = self.line_limit - 1 # apply bounds

            segments = self.get_segments()

            total_lines = 0 # track total number of lines occupied by box text

            # add lines used by each segment
            for current_string in segments:
                if not current_string: # blank segment => empty line
                    used_lines = 1
                else: # partially filled lines count as a full line
                    used_lines = math.ceil(len(current_string) / self.line_length)
                total_lines += used_lines # update total

            # truncate string if line capacity is surpassed
            if total_lines > (self.extra_lines + 1):
                overflow = total_lines - (self.extra_lines + 1) # lines that surpass box bounds
                # remove overflowed lines
                for i in range(overflow):
                    self.remove_line()

    def new_prompt(self,prompt):
        new_prompt = prompt[:self.line_length] # prompt may be one line max
        # update prompt in string
        if not self.string:
            self.string = new_prompt
        else:
            self.string = self.string.replace(self.prompt,new_prompt,1) # swap prompts (update string)
        self.prompt = new_prompt # save new prompt
        self.prompt_size = len(self.prompt)
        self.update_lines() # in case new prompt length shifts box

    # create a list of substrings from the box text, split at newlines
    def get_segments(self):
        # add temporary char [!] so that an extra (empty) segment will be created in case the string ENDS with a newline
        segments = (self.string + '!').splitlines() # there will be at least 1 segment always

        # now delete the temp char so that it does not disrupt the amount of characters in this segment
        segments[-1] = segments[-1][:-1]

        return segments

    # replace newline characters with whitespace as filler text to expand box dimensions
    def skip_lines(self):
        segments = self.get_segments() # separated at newlines
        text = '' # full string with filler spaces
        for i in range(len(segments)):
            if i > 0:
                # add enough spaces so that this segment will begin on the next empty line
                # full line of spaces minus number of chars of previous segment (only chars on a partially filled line count)
                whitespace = self.line_length - (len(segments[i-1]) % self.line_length)
                text += ' ' * whitespace
            text += segments[i] # add next line of text
        return text

    # deletes the most recent line of text in the box
    def remove_line(self):
        # sections of the string cut where a newline is
        segments = self.get_segments()

        # remove line from last segment:
        characters = len(segments[-1])  # 0 indicates empty line => string ends with newline

        # more than a line of text
        if characters > self.line_length:
            # remove marked text from segment -- enough characters to leave behind a whole number of lines
            marked_text = characters % self.line_length
            # if there is already a whole number of lines, delete an entire line instead
            if marked_text == 0:
                marked_text = self.line_length
            segments[-1] = segments[-1][:-(marked_text)] # trim text
        # less than or exactly a line of text
        else:
            # delete rest of this segment
            segments.pop() # do not preserve a newline (by keeping empty segment) -- puts cursor at the end of the previous line

        # reattach segments to form new string (the segments were split at newlines)
        # if the last segment was erased, so was the last newline character
        self.string = '\n'.join(segments)

        # restore prompt in case it was erased
        if not self.string:
            self.string = self.prompt

    def clear_illegal_chars(self,string,fallback='*'):
        # replace undefinded characters with a substitute
        return ''.join(ch if ch in self.available_chars else fallback for ch in string)

    def paste(self):
        new_string = pyperclip.paste()
        self.string += self.clear_illegal_chars(new_string)

    def change_string(self,new_string=''):
        # overwrite current box contents with a new string
        self.string = self.prompt + new_string
        self.update_lines()

    def input(self,char_code):
        # Decipher character code enter by the user:
        # BACKSPACE
        if char_code == 8:
            if len(self.string) > self.prompt_size:
                self.string = self.string[:-1] # remove one character

        # Alt + BACKSPACE = clear box
        elif char_code == 504:
            self.string = self.prompt # clear box

        # Ctrl + c = copy
        elif char_code == 3:
            pyperclip.copy(self.string[self.prompt_size:]) # add box contents to clipboard (exclude prompt)

        # Ctrl + v = paste
        elif char_code == 22:
            self.paste()

        # Tab = indent
        elif char_code == 9:
            self.string += ' ' * self.tabsize

        # Ctrl + ENTER = add line
        elif char_code == 529:
            self.string += '\n' # skip line

        # Ctrl + BACKSPACE = remove line
        elif char_code == 127:
            self.remove_line()

        else: # OTHER CHARACTER
            new_char = chr(char_code) # convert to character (str)
            # check for a NUMBER or LETTER or SPECIAL character
            if new_char in self.available_chars:
                self.string += new_char # ADD character

        # Re-calculate extra lines
        self.update_lines() # restricts string if line limit is reached

    def enter(self):
        # ENTER was pressed
        self.output = self.string[self.prompt_size:] # exclude prompt in output
        self.string = self.prompt # reset string
        # shrink box to original height
        self.extra_lines = 0
        self.shift() # drop extra lines
        return self.output

    def switch_color(self,state):
        self.color_on = state # on/off
        # update current state
        if self.color_on:
            self.window.attron(self.color) # turn ON box color
        else:
            self.window.attroff(self.color) # turn OFF box color

    def set_color(self,c):
        try:
            # deactivate previous window color
            self.window.attroff(self.color)
            # activate new color
            self.window.attron(c)
            # save new color information
            self.color = c
            # cannot turn on color right now
            if not self.color_on:
                self.window.attroff(self.color) # shut off new color (we know it works)
        except: # default display
            self.color = curses.color_pair(0)

    def display(self):
        self.window.erase()
        # create a box around the window
        self.window.box()
        # fill box contents
        y = 1
        x = self.margin
        n = self.line_length # safety, prevent drawing more characters than can fit in the box
        k = 0 # index of next segment of the string
        text = '' # portion of the string that makes up the current line

        # remove box top to indicate part of box is off-screen
        if self.offset_y > 0:
            self.window.addstr(0, 0, ' '*self.width) # overwrite first row with spaces

        # start from first rendered line (skip down offset lines)
        k = self.line_length * self.offset_y

        # temporary string that replaces newlines with whitespace to fill out box dimensions
        temp_string = self.skip_lines()

        # Add the current message the user wrote (in-progress):
        # from first rendered line to the bottom, total_lines = extra_lines + first_line
        for i in range(self.offset_y, self.extra_lines + 1):
            # # second line (indent)
            # if i == 1:
            #     text = '─' * (self.prompt_size-1) + ' ' + self.string[k:(k+self.line_length-self.prompt_size)] # prepend space as large as prompt
            # # extra line
            # else:
            text = temp_string[k:(k+self.line_length)] # add full line (empty if start of newline)
            # paint characters
            try:
                self.window.addnstr(y, x, text, n)
            except:
                self.window.addnstr(y, x, text, n, curses.color_pair(0)) # default display
            # get next position
            y += 1 # skip line
            k += len(text) # find pos of next line of text

        # adjust cursor pos to fit within box (in case box limit reached)
        cursor_y, cursor_x = self.window.getyx()
        text_bounds = (self.width - 1) - self.margin # column text cannot surpass
        if cursor_x > text_bounds:
            cursor_x = text_bounds
            # move cursor to last available space (already filled)
            self.window.move(cursor_y,cursor_x)

        # Add to display screen (mark for refresh):
        # start copying box from upper-left corner => (0,0)
        # paste box inside specified margins relative to the main window
        # - upper-left corner of frame = (self.y,self.x)
        # - lower-right corner of frame = (bounds_y,bounds_x)
        bounds_y = self.y + self.height - 1 # height starts at self.y => -1
        bounds_x = self.x + self.width - 1 # width starts at self.x => -1
        self.window.noutrefresh(0,0,self.y,self.x,bounds_y,bounds_x) # render section of pad to frame


# Functions:
def make_color(foreground,background):
    global color_num
    curses.init_pair(color_num, foreground, background) # bind color pair to integer
    new_color = curses.color_pair(color_num) # store color data
    color_num += 1 # increment for next color
    return new_color


def start_demo():
    screen = Screen()
    for x in range(1,53): # add 52 rows
        screen.add('Row %s' %x)

    # explain usage
    text = f'''\nHELP:

    Use arrow keys to scroll screen up or down one item.
    LEFT / RIGHT arrows to move up or down a page.
    Press ENTER to return to last item.
    Press HOME to jump to the first item.
    Esc to close the program.
    
    Resizing
    --------

    Cuts off text when screen is smaller than {screen.min_wrapsize} characters wide.

    Input Box
    ---------

    Type any of these available characters:
    {screen.typebox.standard_chars}
    {screen.typebox.special_chars[:-2]}

    TAB adds {screen.typebox.tabsize} spaces.
    BACKSPACE deletes a single character.
    ENTER adds the text from the box to the screen.

    Shortcuts:

        Alt + BACKSPACE = clear box
        Alt + UP/DOWN = cycle through keyboard history
        Ctrl + C = copy text in box to clipboard
        Ctrl + V = paste to box
        Ctrl + ENTER = skip line
        Ctrl + BACKSPACE = delete line
        Alt + D = toggle input box
        Alt + H = toggle cursor
        Alt + Q = toggle color
    '''
    screen.add(text, screen.ATR_HIGHLIGHT)
    # screen.typebox.set_color(screen.green)
    screen.current = 52 - screen.max_lines + 8 # show first bit of help
    # screen.typebox.line_limit = 2
    screen.run()
    screen.close()


if __name__ == '__main__':
    start_demo()

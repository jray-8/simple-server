# Simple Server
import socket
import threading
import pickle
import mycurses
import poem_extractor
import os
import time
from zipfile import ZipFile

# Specify public data [importable] -- constants, classes / objects, functions
__all__ = ['screen','SERVER_NAME','ENCODING','HEADERSIZE','FILE_HEADERSIZE','BUFFERSIZE','FILE_BUFFERSIZE', \
    'MICRO_SLEEP','SUCCESS','FAILURE','DEBUG','HOST','IP','PORT','CPORT', \
    'COMMAND_LIST','PASSIVE_COMMANDS', \
    'Command','cmd_help','cmd_cls','cmd_dc','cmd_list','cmd_find','cmd_tell','cmd_check','cmd_visible','cmd_admin','cmd_become_admin', \
    'cmd_demote','cmd_get_demoted','cmd_kick','cmd_get_kicked','cmd_send','cmd_receive', \
    'announce','get_args','create_file','create_dir','create_zip','extract_files','send_data','upload_file','send_msg','send_pass','send_fail', \
    'check_pass','read_msg','receive_data','download_file']

# Setup Terminal
screen = mycurses.Screen()

SERVER_NAME = 'SYSTEM'
ENCODING = 'utf-8'
HEADERSIZE = 8 # number of bytes prepended to a message for the header
FILE_HEADERSIZE = 10 # bytes prepended to a file msg for the header (used to specify the size of a file)
BUFFERSIZE = 64 # bytes per packet
FILE_BUFFERSIZE = 1024
MICRO_SLEEP = 0.5
SUCCESS = 0
FAILURE = 1
DEBUG = 0

# Address Information -- static
HOST = socket.gethostname()
IP = socket.gethostbyname(HOST)
PORT = 50150 # main port for text interaction
CPORT = 50151 # commands

# |--- Port Ranges ---|
# Well-known: 0-1023
# Registered: 1024-49151
# Dynamic: 49152–65535

# Commands:
class Command():
    def __init__(self,name):
        self.name = name.upper()
        # set these later:
        self.description = '' # what it does
        self.usage = '' # how to use
        self.action = None # function
        # defaults
        self.internal = False # can function without contacting server -- UI effects
        self.passive = False # can only be used by other functions -- cannot be called directly (makes 'restricted' obsolete)
        self.restricted = False # requires admin rights to use
    def show_help(self): # assist the user with this command
        screen.add(self.description)
        parameters = f' {self.usage}' if self.usage else ''
        screen.add()
        screen.add(self.name + parameters)
        screen.add()
        screen.display()
    def execute(self, args=[]):
        if self.internal:
            try:
                self.action(args)
                return SUCCESS
            except Exception as e:
                screen.add(f'Internal Command Error - {self.name} could not execute!', screen.ATR_ALERT)
                if DEBUG:
                    screen.add(str(e)) #!
                screen.display(1)
                return FAILURE

# create commands:
# -- internal --
cmd_help = Command('help')
cmd_help.description = 'Provides help information for Server commands.'
cmd_help.usage = f'{cmd_help.name} [command]\n    command - displays help for that command.\n\
    Type {cmd_help.name} without parameters to view available commands.'
cmd_help.internal = True
def display_help(args):
    # see if the user wants specific help information
    if len(args) <= 1: # general
        name = None
    else: # determine target command
        name = args[1].upper()
        found = False
        for cmd in COMMAND_LIST:
            if not cmd.passive and cmd.name == name:
                found = True
                break # cmd is the chosen command
        if not found: # command name was invalid
            screen.add(f'Could not find help information for \'{args[1]}\'')
            return
    # Show Help:
    # general help information -- list commands + descriptions
    if not name:
        margin = 15 # space until description (+2 space for marker)
        screen.add('To view more information on a specific cmd, type /HELP [command-name]')
        marker = '' # to signify elevated privilege is required
        for cmd in COMMAND_LIST:
            if not cmd.passive:
                marker = '* ' if cmd.restricted else '  '
                screen.add(f'{cmd.name:<{margin}} {marker+cmd.description}', screen.ATR_CRITICAL) # [marker][name + margin] description
        screen.add('\n[*] - These commands require elevated rights to use.\n')
    # specific help information -- description + usage
    else:
        cmd.show_help()
cmd_help.action = display_help # set internal function

cmd_cls = Command('cls')
cmd_cls.description = 'Clears the screen.'
cmd_cls.internal = True
def clear_screen(args):
    screen.clear()
cmd_cls.action = clear_screen

cmd_dc = Command('dc')
cmd_dc.description = 'Disconnect from the Server.'
cmd_dc.internal = False
def disconnect(args):
    screen.add('Disconnecting from the server...')
    screen.quit(1)
cmd_dc.action = disconnect

# -- external --
cmd_list = Command('list')
cmd_list.description = 'Displays a list of all authorized users connected to the Server.'

cmd_find = Command('find')
cmd_find.description = 'Displays the socket address of the chosen user.'
cmd_find.usage = '[username]'

cmd_tell = Command('tell')
cmd_tell.description = 'Send an exclusive message to the chosen user.'
cmd_tell.usage = '[username] [message]'
cmd_tell.restricted = True

cmd_check = Command('check')
cmd_check.description = 'Tests whether a user is free to receive commands.'
cmd_check.usage = '[username]'

cmd_visible = Command('visibility')
cmd_visible.description = 'Show or hide yourself to other users on the server.'
cmd_visible.usage = '[state]\n    States: 0=OFF, 1=ON | You may type the name or value.\n    You cannot be targeted with commands while hidden.'
cmd_visible.restricted = True

cmd_admin = Command('admin')
cmd_admin.description = 'Grants the chosen user elevated privileges.'
cmd_admin.usage = '[username]'
cmd_admin.restricted = True

cmd_become_admin = Command('become_admin')
cmd_become_admin.description = '[Passive] Allows this user to become a Server administrator.'
cmd_become_admin.passive = True # result of admin -- called automatically

cmd_demote = Command('demote')
cmd_demote.description = 'Withdraws a user\'s special privileges.'
cmd_demote.usage = '[username]'
cmd_demote.restricted = True

cmd_get_demoted = Command('get_demoted')
cmd_get_demoted.description = '[Passive] Removes the status of Server administrator from this user.'
cmd_get_demoted.passive = True # result of demote -- called automatically

cmd_kick = Command('kick')
cmd_kick.description = 'Forcibly removes a user from the Server.'
cmd_kick.usage = '[username] [comment]\n    comment (optional) - explain why user was kicked.'
cmd_kick.restricted = True

cmd_get_kicked = Command('get_kicked')
cmd_get_kicked.description = '[Passive] Prevents user from reconnecting.'
cmd_get_kicked.passive = True # result of kick -- called automatically

cmd_send = Command('send')
cmd_send.description = 'Send any file to another user on the Server.'
cmd_send.usage = '[username] [filepath] ...\n    username - name of user you want to send the file to.\n    \
filepath - checks the current directory if full path is not specified.\n\n\
You must encase path in quotes if it contains spaces.\nYou may enter multiple paths in succession and they will be zipped together before sending.'

cmd_receive = Command('receive')
cmd_receive.description = '[Passive] Receive an incoming file request from an active user.'
cmd_receive.usage = '[username] [filename] [server-side filepath]' # not for clients
cmd_receive.passive = True # result of send -- called automatically

def get_cmd_name(cmd):
    return cmd.name
COMMAND_LIST = [cmd_help,cmd_cls,cmd_dc,cmd_list,cmd_find,cmd_tell,cmd_check,cmd_visible,cmd_admin,cmd_become_admin,\
                cmd_demote,cmd_get_demoted,cmd_kick,cmd_get_kicked,cmd_send,cmd_receive]
COMMAND_LIST.sort(key=get_cmd_name) # sort alphabetically
PASSIVE_COMMANDS = [z.name for z in COMMAND_LIST if z.passive] # names of passive commands (in lowercases)

# Public Functions:
def announce(name,msg=''):
    return f'[{name}]: {msg}'

def get_args(cmd,clear_symbols=False):
    # parse a command string and separate it into readable components
    # delimit by whitespace, preserve substrings within double-quotes
    # clear_symbols - determines if the final args will keep their outer quotes
    args = []
    tokens = cmd.split() # all substrings isolated by whitespace
    composite_arg = '' # argument made of multiple tokens (enclosed in double-quotes)
    str_linking = False # determines if next token should be included with the current arg
    state_change = False # determines if current token has changed the state of string linking
    # eg. "" (open/close) = state not changed, """ (open/close/open) = state changed
    
    current_pos = 0 # track index of current token
    # location of composite argument
    start = 0
    end = 0

    # extract args
    for x in tokens:
        current_pos = cmd.index(x,current_pos) # only start checking from end of previous token

        # check for double-quotes
        if x.count('"') % 2 == 1: # quotes open/closed
            state_change = True
        else: # state unchanged (or swap/swaped back)
            state_change = False
        
        # linking start/end
        if state_change:
            # start linking
            if not str_linking:
                start = current_pos # remember this index
                str_linking = True

            # finish linking
            else:
                end = current_pos + len(x) # will not include final indexed char
                str_linking = False # stop linking
                # build composite arg
                composite_arg = cmd[start:end]
                if clear_symbols:
                    composite_arg = composite_arg.strip('"')
                args.append(composite_arg) # add composite

        else: # same state
            if not str_linking: # arg = token
                args.append(x) # add arg
            else: # keep linking until finished
                pass

        current_pos += len(x) # skip past the current token, so the next pos will not index the same substring again

    # case: ended while linking (link not closed)
    if str_linking:
        composite_arg = cmd[start:] # rest of string is attached
        if clear_symbols:
            composite_arg = composite_arg.strip('"')
        args.append(composite_arg)

    #! show args
    if DEBUG > 1:
        screen.add('Args: ' + str(args), screen.ATR_DEBUG)
    return args

def create_file(name,destination=''):
    # attempt to create the file at the target destination
    # if a file with the same name exists, increment the filename until it is unique
    if not destination: # use current directory [default] 
        destination = os.getcwd()

    i = 1 # track attempts made
    root, extension = os.path.splitext(name)
    path = os.path.join(destination,name)

    # file already exists -- folder counts as a file
    while os.path.exists(path):
        i += 1 # increment name -- example (i).txt
        name = f'{root} ({str(i)}){extension}' # new name
        path = os.path.join(destination,name) # update path

    # name is now unique
    try:
        open(path,'x').close()
    except Exception as e:
        screen.add(f'Create File Error - could not create: \'{name}\'', screen.ATR_CRITICAL)
        screen.add(str(e))
        screen.display(1)
        return '' # indicates failure
        
    # return successful name of file
    return name

def create_dir(name,destination=''):
    # attempt to create a new directory at destination
    # if another dir with the same name exists, increment the folder name until it is unique
    if not destination:  # use current directory [default] 
        destination = os.getcwd()

    i = 1 # track attempts made
    path = os.path.join(destination,name)

    # directory already exists -- or file with same name
    while os.path.exists(path):
        i += 1 # increment name -- folder (i)
        name = f'{name} ({str(i)})' # new name
        path = os.path.join(destination,name) # update path

    # name is now unique
    try:
        os.mkdir(path)
    except Exception as e:
        screen.add(f'Create Directory Error - could not create: \'{name}\'', screen.ATR_CRITICAL)
        screen.add(str(e))
        screen.display(1)
        return '' # indicates failure
        
    # return successful name of directory
    return name

def create_zip(target_list,destination=''):
    # create a zip file of all target elements (can be single or multiple files and/or directories)
    # save new file to destination

    # use current directory by default
    if not destination:
        destination = os.getcwd()

    # make sure input is a list
    if isinstance(target_list, list) == False:
        target_list = [target_list]

    # create zip file at destination
    filename = os.path.basename(target_list[0]) # use same zip name as first targeted file or directory
    filename = os.path.splitext(filename)[0] + '.zip' # add zip extension (replace alternate ext if file)
    filename = create_file(filename, destination)
    if not filename:
        return '' # error

    # path to new zip file
    zip_path = os.path.join(destination,filename)

    # open zip
    try:
        z = ZipFile(zip_path,'w')
    except Exception as e:
        screen.add(f'Zip Error - could not open: \'{zip_path}\'', screen.ATR_CRITICAL)
        screen.add(str(e))   

    # archive items
    for target in target_list:

        # structure archived directories relative to the containing dir -- only create folders that exist beyond the target's own dir
        target_dir = os.path.dirname(target) # if target is a directory, it will be included in the zip as a main folder

        # compress and add target to archive
        try:
            # add single file
            if os.path.isfile(target):
                z.write(target, arcname=os.path.relpath(target,target_dir))
            # add entire directory
            elif os.path.isdir(target):
                for root, dirs, files in os.walk(target):
                    for name in files:
                        new_path = os.path.join(root,name)
                        # only directories that appear after the target directory will be replicated (added to archive name)
                        z.write(new_path, arcname=os.path.relpath(new_path,target_dir))
            # target DNE
            else:
                raise Exception('Target path does not exist.')
        except Exception as e:
            z.close() # stop writing to file
            screen.add(f'Zip Error - could not archive: \'{target}\'', screen.ATR_CRITICAL)
            screen.add(str(e))
            try: # delete corrupt file
                os.remove(zip_path)
            except Exception as e:
                screen.add('Zip Error - removing corrupt zip.', screen.ATR_ALERT)
                screen.add(str(e))
            screen.display(1)
            return ''
            
    # close file
    z.close()

    # if successful, return path to zip file
    return zip_path

def extract_files(new_zip,destination='',remove_zip=True):
    # attempt to extract all files from the zip to a folder (of the same name) at destination
    if not destination:  # use current directory [default] 
        destination = os.getcwd()

    # extract all contents to chosen destination
    try:
        z = ZipFile(new_zip,'r')
        z.extractall(destination)
    except Exception as e:
        screen.add(f'Extract Error - could not unzip: \'{new_zip}\'', screen.ATR_CRITICAL)
        screen.add(str(e))
        screen.display(1)
        return ''
    # close file
    finally:
        z.close()

    # delete zip file (contents were extracted and saved elsewhere)
    if remove_zip:
        try:
            os.remove(new_zip)
        except Exception as e:
            screen.add('Extract Error - removing old zip.', screen.ATR_ALERT)
            screen.add(str(e))
            screen.display(1)
    
    # successful extraction, return location of extracted contents
    return destination

def send_data(sock,data,attr=screen.ATR_DYNAMIC): # input is bytes
    # Add header to data -- property [2 bytes] + color [2 bytes] + size of message [4 bytes] (remaining bytes)
    # size:
    size = len(data)
    msg_len = str(size)
    if len(msg_len) > (HEADERSIZE-4): # header not large enough to specify msg length
        screen.add(f'Send Error -  HEADERSIZE not large enough to specify msg length - must be less than 10^{HEADERSIZE-4} bytes!', screen.ATR_ALERT)
        return FAILURE
    # property and color:
    try:
        # only take last 2 digits of given, pad with 0s on the left if only 1 digit is found
        p = f'{str(attr[0])[-2:]:0>2}'
        c = f'{str(attr[1])[-2:]:0>2}'
    except Exception as e:
        screen.add('Send Error -  invalid attribute argument!', screen.ATR_ALERT)
        screen.add(str(e))
        return FAILURE
    header = p + c + msg_len
    package = bytes(f'{header:<{HEADERSIZE}}', ENCODING) + data # prepend a left-aligned header to the data
    # Send package [bytes]
    try:
        sock.send(package)
    except Exception as e:
        screen.add('Send Error -  connection aborted!', screen.ATR_ALERT)
        screen.add(str(e))
        return FAILURE
    return SUCCESS

def upload_file(sock,path,show_progress=True): # input is file path -- sends file while reading
    # assumes valid path
    with open(path,'rb') as file: # close file automatically
        size = os.path.getsize(path)
        msg_len = str(size) # size of file in words
        bytes_sent = 0
        if show_progress:
            old_prompt = screen.typebox.prompt
        # create header
        if len(msg_len) > FILE_HEADERSIZE: # header not large enough to hold length of file (each byte of msg_len represents another ^10 bytes of file size)
            # send a header of 0 to indicate failure
            header = f'{0:<{FILE_HEADERSIZE}}'
            sock.send(bytes(header,ENCODING))
            screen.add(f'Upload File Error - FILE_HEADERSIZE not large enough to specify file length - must be less than 10^{FILE_HEADERSIZE} bytes!', screen.ATR_ALERT)
            return FAILURE
        try:
        # send header
            header = f'{size:<{FILE_HEADERSIZE}}'
            sock.send(bytes(header,ENCODING))
        # start sending file:
            data = file.read(FILE_BUFFERSIZE)
            while data:
                sock.send(data)
                # show progress bar
                if show_progress:
                    bytes_sent += len(data)
                    screen.typebox.new_prompt(f'Uploading... [{int((bytes_sent/size)*100)}%] | ')
                    screen.display()
                data = file.read(FILE_BUFFERSIZE) # get next packet
        except Exception as e:
            screen.add('Upload File Error - connection aborted!', screen.ATR_ALERT)
            screen.add(str(e))
            return FAILURE
        # Finished (sent full file)
        # restore prompt
        if show_progress:
            screen.typebox.new_prompt('Upload Complete! | ')
            screen.display()
            time.sleep(1) #$
            screen.typebox.new_prompt(old_prompt)
            screen.display()
        return SUCCESS

def send_msg(sock,msg,attr=screen.ATR_DYNAMIC): # input is a string -- encodes for you
    return send_data(sock,bytes(msg,ENCODING),attr)

def send_pass(sock):
    send_msg(sock,'PASS')

def send_fail(sock):
    send_msg(sock,'FAIL')

def check_pass(data): # must be used in a try/except block
    read_data = False
    try:
        response = data.decode(ENCODING)
        read_data = True # successfully decoded data
        if response == 'PASS':
            return SUCCESS
        elif response == 'FAIL':
            return FAILURE
        else:
            raise Exception('Unexpected response received for pass.')
    except Exception:
        # re-raise exception to next layer of scope
        if read_data:
            raise
        else: # corrupt data
            raise Exception('Corrupt data checked for pass.')

def read_msg(data,attr):
    move_screen = 0
    if screen.is_latest(): # (if already on bottom) bring screen down to see new msg
        move_screen = 1
    screen.add(data.decode(ENCODING),attr)
    screen.display(show_latest=move_screen) # update screen without user input

# continually receives data and performs an action on it -- if no action is given the first message read is returned
def receive_data(sock,action=None,get_feature=False):
    full_msg = b''
    new_msg = True # can start to read a new msg (i.e. not in the middle of reading another msg)
    header = '' # size of new message in bytes - string
    size = 0
    attr = screen.ATR_DYNAMIC
    leftover_bytes = False
    # Start receiving packets from the stream
    while True:
        if not leftover_bytes:
            try:
                data = sock.recv(BUFFERSIZE) # receive data in packets of x bytes
            except Exception as e:
                if DEBUG:
                    screen.add('Err.4 - Connection terminated!', screen.ATR_ALERT)
                    screen.add(str(e))
                    screen.display(1)
                return FAILURE
        else:
            leftover_bytes = False # use them up this iteration

        # Read Header
        if new_msg:
            remaining_data = HEADERSIZE-len(header) # how many bytes remain until the header is fully received
            if remaining_data > len(data): # not last packet for the header
                header += data.decode(ENCODING)
            else: # final packet
                header += data[:remaining_data].decode(ENCODING)
                # Header has been received
                try:
                    p = int(header[:2]) # property
                    c = int(header[2:4]) # color
                    size = int(header[4:]) # get size of message
                    attr = (p,c)
                except Exception as e:
                    if DEBUG:
                        screen.add(f'Receive Error -  could not interpret header.', screen.ATR_ALERT)
                        screen.add(str(e))
                        screen.display(1)
                    header = '' # erase faulty header
                    return FAILURE
                if DEBUG > 1: # show size of msg
                    screen.add(f'*** Receiving New Message - [{size}] bytes ***', screen.ATR_DEBUG) #!
                    screen.display(1)
                new_msg = False 
                # Handle excess data (if any)
                data = data[remaining_data:]

        # Read Data
        if not new_msg:
            # Append data
            remaining_data = size-len(full_msg)
            if remaining_data > len(data): # not the last packet for the message
                full_msg += data
            else: # final packet
                full_msg += data[:remaining_data] # add only as much data as the msg length specified
                # Full message has been received:
                if DEBUG > 1:
                    screen.add(f'*** Message Received! ***', screen.ATR_DEBUG) #!
                    screen.display(1)
                if action:
                    if get_feature:
                        action(full_msg,attr) # perform task on the encoded package
                    else:
                        action(full_msg)
                else: # no action (return data)
                    output = (full_msg,attr) if get_feature else full_msg # attach or omit attribute
                    return output # send package to caller
                header = ''
                size = 0
                full_msg = b''
                new_msg = True
                # Handle excess data (if any)
                data = data[remaining_data:]
                leftover_bytes = True

# collect and assemble a file from the socket connection -- write to file as the data is read
def download_file(sock,destination,show_progress=True): # assume valid download path is given (destination)
    header = '' # full size of file
    size = 0
    bytes_read = 0 # how much of the file has been received
    if show_progress:
        old_prompt = screen.typebox.prompt
    # Open empty file -- close automatically on failure
    with open(destination,'wb') as file:
        # Start receiving chunks of data
        while True:
            try:
                data = sock.recv(FILE_BUFFERSIZE) # receive data in packets of x bytes
            except Exception as e:
                screen.add('Download File Error - connection aborted.', screen.ATR_ALERT)
                screen.add(str(e))
                screen.display(1)
                return FAILURE

            # Read Header -- safely assume header is smaller than the file buffer size
            if not header:
                header = data[:FILE_HEADERSIZE].decode(ENCODING)
                try:
                    size = int(header)
                    if size <= 0: # must be concrete message
                        raise Exception('Received file size of 0.')
                    if DEBUG > 1:
                        screen.add(f'*** Incoming File - [{size}] bytes ***', screen.ATR_DEBUG) #!
                        screen.display(1)
                except Exception as e:
                    screen.add('Download File Error - could not interpret header.', screen.ATR_ALERT)
                    screen.add(str(e))
                    screen.display(1)
                    return FAILURE
                # Remove header from packet so that excess data from this packet can be written immediately
                data = data[FILE_HEADERSIZE:]

            # Read File
            if header:
                # Build file
                remaining_data = size - bytes_read # how many more bytes need to be delivered
                # do not add excess data to the file (in case more data appears in the stream after the file is finished)
                data = data[:remaining_data]
                file.write(data) # save data to file
                bytes_read += len(data)
                # show progress bar
                if show_progress:
                    screen.typebox.new_prompt(f'Downloading... [{int((bytes_read/size)*100)}%] | ')
                    screen.display()

                 # Finished (read entire file)
                if bytes_read == size:
                    if DEBUG > 1: # show bytes read
                        screen.add(f'*** File Received - [{(bytes_read)}/{size}] bytes read ***', screen.ATR_DEBUG) #!
                        screen.display(1)
                    # restore prompt
                    if show_progress:
                        screen.typebox.new_prompt('Download Complete! | ')
                        screen.display()
                        time.sleep(1) #$
                        screen.typebox.new_prompt(old_prompt)
                        screen.display()
                    # file is complete
                    file.close()
                    return SUCCESS
                elif bytes_read > size: # wrote excess data to the file
                    screen.add('Download File Error - data overflow.', screen.ATR_ALERT)
                    screen.display()
                    return FAILURE


# Run only if this is being used as the server, NOT imported by the client
if __name__ == '__main__':

    # create an endpoint for the server
    SERVER_SOCKET = socket.socket(socket.AF_INET,socket.SOCK_STREAM) # for standard messages
    COMMAND_SOCKET = socket.socket(socket.AF_INET,socket.SOCK_STREAM) # for command processing
    DOWNLOAD_FOLDER = 'downloads'
    HIDDEN_CHARS = '*'
    MAX_USERS = 10
    # make sure download folder is accessible
    if not os.path.isdir(DOWNLOAD_FOLDER):
        try:
            os.mkdir(DOWNLOAD_FOLDER) # create folder
            screen.add(f'Successfully created DOWNLOAD FOLDER: \'{DOWNLOAD_FOLDER}\'\n', screen.ATR_SUCCESS)
        except Exception as e: # failed
            screen.add('Could not create DOWNLOAD FOLDER.', screen.ATR_ALERT)
            screen.add(str(e))
            screen.display(1)
            screen.pause()
            # close program now
            screen.close()
            exit(3)

    client_list = []
    reserved_names = [SERVER_NAME] # uppercase only, users cannot choose these names
    hidden_names = [] # names of hidden users
    # control access to shared resources (between threads):
    name_lock = threading.Lock()
    delivery_lock = threading.Lock()
    # additional resources
    the_raven = poem_extractor.Extractor('resources/the_raven.txt')

    class Client():
        def __init__(self,socket,address):
            self.sock = socket
            self.address = address # (IP, port)
            # needs authorization:
            self.username = ''
            self.cmd_sock = None
            self.cmd_address = None
            self.hidden = False
            self.active = False # become active once authorized
            self.command_lock = threading.Lock() # processing a cmd
            # use lock because multiple instances may be waiting for the command port at once (accept one at a time).YY

        # create a msg revealing the endpoint of this client's main connection
        def get_location(self):
            return f'{self.username} is connected from - {self.address[0]}:{self.address[1]}'

        def authorize(self):
            # Stage 1)
            welcome_msg = 'Welcome to the Simple Server!'
            try:
                send_msg(self.sock, welcome_msg, screen.ATR_SUCCESS) # welcome new user
                confirmation = receive_data(self.sock) # confirm the user received the welcome msg to advance
                if check_pass(confirmation) == FAILURE:
                    raise Exception('PASS failed!')
            except Exception as e:
                screen.add('Authorization Error - Stage 1 <welcome msg>', screen.ATR_ALERT)
                screen.add(str(e))
                return FAILURE

            # Stage 2)
            approved = False
            try:
                while not approved:
                    #$ hide names of hidden users
                    taken_names = [k if k not in hidden_names else HIDDEN_CHARS * len(k) for k in reserved_names]
                    data = pickle.dumps(taken_names)
                    send_data(self.sock,data) # list of unavailable usernames
                    # receive username
                    data = receive_data(self.sock)
                    name = data.decode(ENCODING)
                    # check name
                    name_lock.acquire() # only 1 user may be checked at a time (incase they try the same name)
                    if name not in reserved_names: # valid name
                        reserved_names.append(name)
                        name_lock.release() # next user may be checked since the list was already updated
                        self.username = name # add identity to client
                        send_pass(self.sock) # send approval
                        approved = True
                    else: # invalid
                        name_lock.release() # list did not change
                        send_fail(self.sock) # send disapproval
                        # wait for user to request another attempt
                        request = receive_data(self.sock)
                        if check_pass(request) == FAILURE:
                            raise Exception('Username was disapproved and request for a new name was not made.')
            except Exception as e:
                screen.add('Authorization Error - Stage 2 <username>', screen.ATR_ALERT)
                screen.add(str(e))
                return FAILURE

            # Stage 3)
            try:
                # did the client connect to the command socket
                confirmation = receive_data(self.sock) # wait here...
                if check_pass(confirmation) == FAILURE: 
                    raise Exception('PASS failed')
                # stage complete -- this client now has a cmd socket connection
            except Exception as e:
                screen.add('Authorization Error - Stage 3 <cmd connection>', screen.ATR_ALERT)
                screen.add(str(e))
                return FAILURE

            # Stage 4)
            status = f'Server Status: [{count_active_users()+1}/{MAX_USERS}] active users' # includes this user
            msg = status + '\nUse / to enter commands, // to create notes, /help for more info.\n'
            try:
                send_msg(self.sock,msg,screen.ATR_HIGHLIGHT)
                confirmation = receive_data(self.sock) # do not contact the client until they have received the last msg successfully
                if check_pass(confirmation) == FAILURE:
                    raise Exception('PASS failed!')
            except Exception as e:
                screen.add('Authorization Error - Stage 4 <server status>', screen.ATR_ALERT)
                screen.add(str(e))
                screen.pause(1)
                return FAILURE
            # COMPLETE
            return SUCCESS


    # private functions:
    def broadcast(data, attr=screen.ATR_DYNAMIC):
        delivery_lock.acquire() # block other calls until released
        for c in client_list:
            if not c.active: # this user has not been authorized yet
                continue
            send_data(c.sock,data,attr) # prepends header
        delivery_lock.release() # next call in line can proceed

    def server_broadcast(msg, attr=screen.ATR_SUCCESS, echo=True): # input is msg (encodes for you)
        # prepend server name
        msg = announce(SERVER_NAME, msg)
        if echo: # show on server-side
            screen.add(msg, attr)
            screen.display(1)
        # encode and announce msg to all users
        x = bytes(msg, ENCODING)
        broadcast(x, attr)

    def deliver_news(msg):
        if msg[:2] == '//': # note
            screen.add(f'Note: {msg[2:]}', screen.ATR_DIM)
        elif msg[0] == '/': # command
            execute_command(msg[1:])
        else:
            # broadcast news
            server_broadcast(msg)

    # allows the server to send commands directly to clients -- some have different operations
    def execute_command(cmd): # display is updated automatically after enter
        # show command
        screen.add('> /' + cmd)
        args = get_args(cmd)
        try:
            name = args[0].upper() # compare in caps
        except:
            screen.add('No command entered.')
            return 1

        # Execute based on name:

        # Cls
        if name == cmd_cls.name:
            screen.clear() # blank screen
            screen.add('+++ Screen Clear +++', screen.ATR_APPROVE)

        # Clall
        elif name == 'CLALL':
            erase_screens() # clear the screen of all users
            server_broadcast('+++ Screen Clear +++', attr=screen.ATR_APPROVE, echo=False)
            screen.add('Cleared all client screens!')
            
        # List
        elif name == cmd_list.name:
            screen.add(list_users(1)) # see hidden

        # Reserve name
        elif name == 'RESERVE':
            title = args[1].upper()
            name_lock.acquire()
            if title not in reserved_names:
                reserved_names.append(title)
            name_lock.release()
            screen.add(f'{title} is now reserved.')

        # Release name
        elif name == 'RELEASE':
            title = args[1].upper()
            name_lock.acquire()
            if title in reserved_names:
                reserved_names.remove(title)
            name_lock.release()
            screen.add(f'{title} is now available.')

        # aliases for visibility
        elif name in ['SHOW', 'HIDE']:
            try:
                x = args[1]
            except:
                x = ''
            if name == 'HIDE':
                state = 0
            else:
                state = 1
            # execute formatted command
            execute_command(f'{cmd_visible.name} {x} {state}')

        # 1 arg - username
        elif name in [cmd_find.name,cmd_tell.name,cmd_check.name,cmd_visible.name,cmd_admin.name,cmd_demote.name,cmd_kick.name]:
            # error handling:
            try:
                username = args[1].upper() # compare to uppercases
            except:
                screen.add('User not entered.')
                return 1
            # find user
            target_client = find_user(username)
            if not target_client:
                screen.add('That user does not exist!')
                return 1

            # perform command ON target:
            # Find
            if name == cmd_find.name:
                screen.add(target_client.get_location())
            # Check
            elif name == cmd_check.name:
                if target_client.command_lock.locked():
                    screen.add(f'{target_client.username} is in a command.')
                else:
                    screen.add(f'{target_client.username} is free.')
            # Visibility
            elif name == cmd_visible.name:
                output = f'{target_client.username} '
                try:
                    state = args[2].lower()
                    # Hide
                    if state in ['0','off']:
                        if not target_client.hidden:
                            target_client.hidden = True
                            hidden_names.append(target_client.username)
                            output += 'was made invisible.'
                            msg = 'Your presence has been made private! Users cannot target you.'
                            send_msg(target_client.sock,announce(SERVER_NAME,msg), screen.ATR_HIGHLIGHT)
                        else:
                            output += 'is already hidden.'
                    # Show
                    elif state in ['1', 'on']:
                        if target_client.hidden:
                            target_client.hidden = False
                            hidden_names.remove(target_client.username)
                            output += 'was made visible.'
                            msg = 'Your presence has been made public! Users may target you.'
                            send_msg(target_client.sock,announce(SERVER_NAME,msg), screen.ATR_HIGHLIGHT)
                        else:
                            output += 'is already visible.'
                    # Invalid State
                    else:
                        raise
                    # Show output
                    screen.add(output)
                except:
                    screen.add('Invalid state. 0=OFF, 1=ON')
                    return 1
            # Kick
            elif name == cmd_kick.name:
                msg = f'[{SERVER_NAME}]: You are being kicked from the server'
                # get optional reason
                if len(args) > 2:
                    reason = cmd[cmd.index(args[2]):] # everything after and including 2rd arg
                    msg += f': {reason}'
                else:
                    msg += '.'
                # remove target
                kick_thread = threading.Thread(target=kick_client,args=(target_client,msg),daemon=True)
                kick_thread.start() # waits until user is free, then removes them
                
            # perform command WITH target:
            else:
                #$ check if free
                wait_time = 15 
                p = screen.typebox.prompt
                screen.typebox.new_prompt(f'[<15s] Waiting for {target_client.username}... ')
                screen.display(1)
                if poll_activity(target_client,timeout=wait_time) == FAILURE:
                    screen.add('That user is busy right now...')
                    screen.typebox.new_prompt(p)
                    return 1
                screen.typebox.new_prompt(p)

                # Tell
                if name == cmd_tell.name:
                    try: # check msg exists
                        args[2]
                    except Exception as e:
                        screen.add('Message not entered!')
                        return 1
                    msg = cmd[cmd.index(args[2]):]
                    send_msg(target_client.sock,'From ' + announce(SERVER_NAME,msg), screen.ATR_DIM)
                    screen.add(f'Delivered message to {target_client.username}.')
                # Admin
                elif name == cmd_admin.name:
                    send_msg(target_client.cmd_sock,'become_admin')
                    screen.add(f'{target_client.username} was made admin.')
                # Demote
                elif name == cmd_demote.name:
                    send_msg(target_client.cmd_sock,'get_demoted')
                    screen.add(f'{target_client.username} was demoted.')

        # Quit
        elif name == 'QUIT' or name == 'END':
            global client_list
            server_broadcast('Shutting Down Server...')
            # stop listening to incoming connections
            SERVER_SOCKET.close()
            COMMAND_SOCKET.close()
            # disconnect all clients
            current_users = client_list.copy() # do not alter list while iterating through clients
            for c in current_users:
                try:
                    c.sock.close()
                    c.cmd_sock.close()
                except Exception as e:
                    screen.add('Quit Error - closing connections.', screen.ATR_ALERT)
                    screen.add(str(e))
            # wait until all clients were successfully removed
            x = 0
            while client_list:
                x += 1
                time.sleep(0.5)
                if x >= 30: # 15 seconds
                    screen.add('Quit Error - not all clients cleared in time.', screen.ATR_ALERT)
                    break
            screen.add('The Server has been terminated.\n', screen.ATR_HIGHLIGHT)
            screen.locked = False # server is not active, screen still on until closed (can check reports).
            screen.can_type = False
            screen.typebox.new_prompt('Press Esc to close . . . ')

        # Undefined
        else:
            screen.add('Could not execute.')
            return 1

    # actively check if the client is free to receive commands
    def poll_activity(new_client,period=0.5,timeout=15):
        elapsed_time = 0
        while new_client.command_lock.locked(): # sample
            # check timeout
            if elapsed_time >= timeout:
                return FAILURE
            # wait until next sample
            elapsed_time += period
            time.sleep(period)
        else:
            return SUCCESS

    # find a client from their name (case sensitive)
    def find_user(name):
        global client_list
        # target is the client being searched for
        for target in client_list:
            if not target.active: # this user has not been authorized yet
                continue # skip this user
            elif target.hidden: # cannot be targeted
                continue
            # this is the user
            elif name == target.username:
                return target
        return None # user must not exist

    # get number of authorized clients
    def count_active_users():
        global client_list
        active_users = 0
        for new_client in client_list:
            if new_client.active: # this user
                active_users += 1
        return active_users
                
    # clear the contents of every client screen (if they are free) -- max process time = 30 x [# of clients]
    def erase_screens():
        global client_list
        for c in client_list:
            if not c.active:
                continue
            if poll_activity(c) == SUCCESS:
                c.command_lock.acquire()
                send_msg(c.cmd_sock,'cls')
                c.command_lock.release()
            else:
                continue

    # create a string of the server status and a list of active users
    def list_users(show_hidden=False):
        global client_list
        active_users = 0 # total authorized clients
        total_hidden = 0 # number of hidden users

        # get the name of each client
        name_string = ''
        for c in client_list:
            if not c.active: # this user has not been authorized yet
                continue
            else:
                active_users += 1
            # hidden user
            if c.hidden:
                total_hidden += 1
                if show_hidden: # force show
                    name_string += f'({c.username})' # indicate hidden
                else:
                    name_string += HIDDEN_CHARS * len(c.username)
            # visible
            else:
                name_string += f'{c.username}'
            # separator
            if not c == client_list[-1]:
                name_string += ', '

        # Build output:
        output = f'There are currently [{active_users}/{MAX_USERS}] users online'
        # check if the server is empty
        if active_users <= 0:
            return output + '.'
        # add names of clients
        output += ':\n' + name_string
        output += '\n' # skip line after names

        # report on hidden users
        if total_hidden > 0:
            p = 'is' if total_hidden == 1 else 'are'
            if show_hidden:
                output += f'\n() - hidden users = {total_hidden}'
            else:
                output += f'\n({total_hidden}) {p} hidden.'
        return output

    # delete temp files from download folder
    def clear_downloads():
        for new_file in os.listdir(DOWNLOAD_FOLDER):
            new_path = os.path.join(DOWNLOAD_FOLDER,new_file)
            try:
                os.remove(new_path)
            except Exception as e:
                screen.add(f'Could not remove: \'{new_path}\'', screen.ATR_CRITICAL)
                screen.add(str(e))
                continue

    def accept_connections():
        while True:
            try:
                client_socket, address = SERVER_SOCKET.accept() # blocking call
            except: # server socket closed
                break
            screen.add(f'received connection from {address}', screen.ATR_HIGHLIGHT) # acknowledge connection
            screen.display()
            new_thread = threading.Thread(target=handle_client,args=(client_socket,address,),daemon=True)
            new_thread.start() # take care of new connection as a separate process...

    def configure_commands():
        global client_list
        while True:
            try:
                cmd_socket, cmd_address = COMMAND_SOCKET.accept() # blocking call
            except: # server socket closed
                break
            screen.add(f'incoming CPort connection from {cmd_address}', screen.ATR_HIGHLIGHT) #!
            screen.display(1)
            try:
                # receive name of client connecting
                data = receive_data(cmd_socket)
                name = data.decode(ENCODING)
            except socket.error as e:
                screen.add(f'Unexpected cmd connection - {cmd_address[0]}:{cmd_address[1]}', screen.ATR_ALERT)
                screen.add(str(e))
                screen.display(1)
                continue # disregard this connection

            # find client trying to connect
            found_client = False
            for c in client_list:
                if c.username == name: # this is the user
                    found_client = True
                    break # done checking -- c remains the target client
            if found_client:
                # fill in command details
                c.cmd_sock = cmd_socket
                c.cmd_address = cmd_address
                send_pass(cmd_socket) # success msg
                new_thread = threading.Thread(target=handle_commands,args=(c,),daemon=True)
                new_thread.start() # begin listening for commands...
            else: # user not found
                send_fail(cmd_socket)
                if DEBUG:
                    screen.add(f'Could not find a matching socket for the user - \'{name}\'', screen.ATR_CRITICAL)
                    screen.add(str(e))
                    screen.display(1)

    def handle_client(sock,addr):
        global client_list
        connected_msg = ' has joined the server!'

        # create a new client
        new_client = Client(sock,addr)
        client_list.append(new_client) # add to list

        # authorize the client
        if new_client.authorize() == FAILURE:
            if DEBUG:
                screen.add(f'Authorization Failed - {new_client.address}', screen.ATR_ALERT) #!
            remove_client(new_client) # delete client
            return # kill thread

        # officially recognize client
        new_client.active = True # other users can now interact with this client
        server_broadcast(new_client.username + connected_msg, screen.ATR_SUCCESS) # announce connection, new_client is ready to receive continuously
        
        receive_data(sock,broadcast,True) # start listening to calls from this client...

        # disconnected
        remove_client(new_client)

    def handle_commands(new_client):
        while True:
            # show previous errors
            if DEBUG:
                screen.display(1) #$ jump to recent

            if new_client.command_lock.locked(): # not in command, release lock
                new_client.command_lock.release()
            data = receive_data(new_client.cmd_sock) # receive a new command...
            if data == FAILURE: # disconnected
                return
            new_client.command_lock.acquire() # prevent other commands from contacting this client until finished -- avoids multiple receives (from client)
            cmd = data.decode(ENCODING)
            args = get_args(cmd) # parse command -- assume valid syntax here, should contain all required args
            name = args[0].upper() # every command will have at least a name parameter -- command names are stored in caps

            # initiate cmd process with client -- these commands were delivered by the user
            if name not in PASSIVE_COMMANDS:
                send_data(new_client.cmd_sock,data) # echo command to client cmd handler
                launch = receive_data(new_client.cmd_sock) # wait for client to set up cmd process...
                try:
                    if check_pass(launch) == FAILURE: # cmd refused
                        continue
                except Exception:
                    continue
            else: # process already initiated on client-side -- these commands were sent directly to the user from an alternate process
                pass

            # Evaluate Commands (uppercase names):
            if DEBUG: #! show request
                screen.add(f'Command from {new_client.username} - /{cmd}')
                screen.display(1)

            # List Users
            if name == cmd_list.name:
                output = list_users()
                # send list to caller
                send_msg(new_client.cmd_sock, output)
                # list cmd finished

            # 1 arg - username
            # Find / Tell / Check / Admin / Demote / Kick
            elif name in [cmd_find.name, cmd_tell.name, cmd_check.name, cmd_admin.name, cmd_demote.name, cmd_kick.name]:
                # check username exists and is valid
                username = args[1].upper() # check uppercases
                target_client = find_user(username) # may retrieve self
                # user DNE
                if not target_client:
                    send_msg(new_client.cmd_sock,'That user does not exist!')
                    continue

                output = '?' # answer returned to caller -- update based on command

                # Find Address
                if name == cmd_find.name:
                    output = target_client.get_location()

                # Tell
                elif name == cmd_tell.name:
                    # case: target is the caller
                    if target_client.username == new_client.username:
                        output = 'Stop talking to yourself!'
                    else: # send message directly to target
                        msg = cmd[cmd.index(args[2]):]
                        msg = 'From ' + announce(new_client.username,msg) # format
                        send_msg(target_client.sock, msg, screen.ATR_DIM) # send to main socket
                        output = f'Delivered to {target_client.username}.'

                # Check
                elif name == cmd_check.name:
                    # case: target is the caller
                    if target_client.username == new_client.username:
                        output = 'You are currently occupied with yourself.'
                    else: # test target availability
                        if target_client.command_lock.locked():
                            output = f'{target_client.username} is currently processing a command.'
                        else:
                            output = f'{target_client.username} is available.'

                # Admin
                elif name == cmd_admin.name:
                    # case: target is the caller
                    if target_client.username == new_client.username:
                        output = 'You are already an admin!' # must be an admin to use this command
                    else: # elevate target user:
                        if poll_activity(target_client,timeout=5) == SUCCESS: #$ free
                            send_msg(target_client.cmd_sock,'become_admin') # send command to target user
                            output = f'{target_client.username} was successfully made admin.'
                        else: # client is busy
                            output = f'That user is busy right now...'

                # Demote
                elif name == cmd_demote.name:
                    # case: target is the caller
                    if target_client.username == new_client.username:
                        # must be an admin to use this command (this is how the server knows they have rights)
                        send_msg(new_client.cmd_sock,'You threw away your rights...')
                        send_msg(new_client.cmd_sock,'get_demoted') # send command to self
                        continue
                    else: # denounce target user:
                        if poll_activity(target_client,timeout=5) == SUCCESS: # free
                            send_msg(target_client.cmd_sock,'get_demoted') # send command to target user
                            output = f'{target_client.username} was successfully demoted.'
                        else: # client is busy
                            output = f'That user is busy right now...'

                # Kick
                elif name == cmd_kick.name:
                    # case: target is the caller
                    if target_client.username == new_client.username:
                        send_msg(target_client.cmd_sock,'You cannot kick yourself!')
                        continue
                    # get optional msg
                    if len(args) > 2:
                        reason = cmd[cmd.index(args[2]):] # everything after and including 2rd arg
                    else:
                        reason = ''
                    # send special kick message to the target
                    try:
                        msg = f'[{SERVER_NAME}]: You are being kicked from the server'
                        if reason:
                            msg += f': {reason}' # add reason for kick
                        else:
                            msg += '.'
                    except Exception as e: # user may have already left
                        continue
                    # remove target
                    kick_thread = threading.Thread(target=kick_client,args=(target_client,msg),daemon=True)
                    kick_thread.start() # waits until user is free, then removes them
                    output = f'You have requested to kick {target_client.username} from the server.'

                # ALL -- executes for every cmd in this section
                send_msg(new_client.cmd_sock,output) # send output
                # cmd finished

            # Visibility
            elif name == cmd_visible.name:
                output = '?' # placeholder
                attr = None # attribute of output
                try:
                    visibility = int(args[1]) # should be value
                except Exception as e:
                    if DEBUG:
                        screen.add('Visibility Error - received invalid visibility state.', screen.ATR_ALERT)
                        screen.add(str(e))
                    continue
                # hide / reveal client
                if visibility:
                    if not new_client.hidden: # case, already visible
                        output = 'We can already see you!'
                    else: # reveal client
                        new_client.hidden = False
                        hidden_names.remove(new_client.username)
                        output = 'You revealed yourself back to the server.'
                else:
                    if new_client.hidden: # case, already hidden
                        #output = 'You cannot descend any deeper into the shroud of darkness that plagues the world above you...' #$
                        verse = the_raven.get_verse() # random stanza from The Raven by Edgar Allen Poe
                        output = '\n'
                        for line in verse.splitlines():
                            output += '\t' + line + '\n'
                        attr = screen.ATR_DIM
                    else: # hide client
                        new_client.hidden = True
                        hidden_names.append(new_client.username)
                        output = 'You were made hidden from the server.'
                # send output
                if attr:
                    send_msg(new_client.cmd_sock,output,attr)
                else:
                    send_msg(new_client.cmd_sock,output)

            # Become Admin
            elif name == cmd_become_admin.name:
                continue # occurs on client-side

            # Get Demoted
            elif name == cmd_get_demoted.name:
                continue # occurs on client_side

            # Get Kicked
            elif name == cmd_get_kicked.name:
                continue # occurs on client_side

            # Send File
            elif name == cmd_send.name:
                # check username
                username = args[1].upper() # check uppercases
                valid_user = False
                target_client = find_user(username) # get client
                if target_client:
                    if target_client.username != new_client.username: # target cannot be the caller
                        valid_user = True

                # confirm existence
                if valid_user: # user exists
                    send_pass(new_client.cmd_sock)
                else: # invalid user
                    send_fail(new_client.cmd_sock)
                    continue

                # wait for client to send desired file name (may have been updated)
                filename = receive_data(new_client.cmd_sock).decode(ENCODING) # get file name with extension -- example.txt
                if not filename: # blank if zip error
                    continue

                # prepare download path
                server_filename = create_file(filename, DOWNLOAD_FOLDER) # create new file, name may be updated
                
                # confirm file path was accessed
                if server_filename:
                    send_pass(new_client.cmd_sock)
                else: # failed to create temp file
                    send_fail(new_client.cmd_sock)
                    continue
                download_path = os.path.join(DOWNLOAD_FOLDER, server_filename) # location of server-side download
                # (name may differ from filename if that filename already exists within the download folder)

                # receive full file -- static download folder
                result = download_file(new_client.cmd_sock,download_path,False) # wait...
                # tell sender if the download succeeded
                if result == SUCCESS:
                    send_pass(new_client.cmd_sock)
                else: # failed to download properly
                    if DEBUG:
                        screen.add(f'Could not download: \'{filename}\'', screen.ATR_CRITICAL) #!
                    send_fail(new_client.cmd_sock)
                    continue

                # wait until the client received confirmation -- file downloaded
                receive_data(new_client.cmd_sock)

                # offer file to target user:
                waiting = True
                wait_time = 15 #$
                while waiting:
                    # check if target is available for a command
                    if poll_activity(target_client, timeout=wait_time) == FAILURE: # client is busy
                        if DEBUG:
                            screen.add(f'{target_client.username} is busy and cannot receive file.', screen.ATR_CRITICAL) #!
                        # tell sender the target was busy
                        send_fail(new_client.cmd_sock)
                        # ask sender to continue waiting or stop
                        reply = receive_data(new_client.cmd_sock)
                        try:
                            if check_pass(reply) == SUCCESS:
                                waiting = True # keep waiting
                                wait_time = 30 # increase wait time
                            else: # terminate command
                                break
                        except Exception as e: # reply error
                            if DEBUG:
                                screen.add(str(e),screen.ATR_ALERT)
                            break # terminate command
                    else:
                        waiting = False
                        try: # send command to target user (use quotes in case of spaces)
                            send_msg(target_client.cmd_sock, f'receive {new_client.username} "{filename}" "{download_path}"')
                        except Exception as e:
                            if DEBUG:
                                screen.add('Send File Error - target user has left!', screen.ATR_CRITICAL)
                                screen.add(str(e))
                        # tell sender the request was sent (with or without error)
                        send_pass(new_client.cmd_sock)
                # send cmd is finished.

            # Receive File
            elif name == cmd_receive.name:
                filename = args[2].strip('"') # name of sent file (may have quotes to preserve spaces)
                path = args[3].strip('"') # path to target download
                # check if user accepts and is able to receive file...
                data = receive_data(new_client.cmd_sock)
                try:
                    if check_pass(data) == SUCCESS: # ready to download
                        # send full file to client
                        upload_file(new_client.cmd_sock,path,False)
                except Exception: # do not upload file
                    pass
                try: # delete server-side download file
                    os.remove(path)
                except Exception as e: # could not be deleted
                    if DEBUG:
                        screen.add(f'Could not remove: \'{path}\'', screen.ATR_CRITICAL)
                        screen.add(str(e))
                    continue
                # receive cmd is finished.

            # --- Evaluate Commands --- 

    def kick_client(c,msg):
        cmd = f'get_kicked {msg}'
        c.command_lock.acquire() # wait until the instant the target is available...
        send_msg(c.cmd_sock,cmd) # initiate the client-side kick procedure
        c.command_lock.release()

    def remove_client(c): # automatically called when sock connection fails
        global client_list
        name = c.username
        if c not in client_list: # in case client was already removed
            return
        try:
            # close all connections
            c.sock.close()
            c.cmd_sock.close()
            # delete client records from database
            client_list.remove(c)
            reserved_names.remove(name)
            if DEBUG:
                time.sleep(1) #! ensure announcement is after connection errors
            # announce disconnection
            msg = f'{name} has left the server!'
            server_broadcast(msg, screen.ATR_ALERT)
        except Exception as e:
            screen.add('Err.5 - Closing Connection', screen.ATR_ALERT)
            screen.add(str(e))


    # Initial screen settings for server
    screen.locked = True
    screen.typebox.new_prompt(announce(SERVER_NAME))
    if screen.show_box:
        screen.toggle_typing() # hide input box while connections are established
    screen.output_function = deliver_news # messages entered by the server are broadcasted to all users

    # attempt to bind the sockets to the specified addresses so they can accept incoming connections on those addresses
    try:
        SERVER_SOCKET.bind((IP, PORT))
        screen.add(f'Server socket sucessfully bound to {IP}:{PORT}', screen.ATR_SUCCESS)
    except socket.error as e:
        # could not start server on desired endpoint
        screen.add(f'Err.1 - Server socket could not bind to {IP}:{PORT}', screen.ATR_ALERT)
        screen.add(str(e))
        screen.pause(1)
        exit(1)

    try:
        COMMAND_SOCKET.bind((IP, CPORT))
        screen.add(f'Command socket sucessfully bound to {IP}:{CPORT}', screen.ATR_SUCCESS)
        screen.add()
    except socket.error as e:
        # could not start server on desired endpoint
        screen.add(f'Err.2 - Command socket could not bind to {IP}:{CPORT}', screen.ATR_ALERT)
        screen.add(str(e))
        screen.pause(1)
        exit(2)

    # prepare to listen for connections (max. queue of 5)
    SERVER_SOCKET.listen(5)
    COMMAND_SOCKET.listen(5)
    screen.add('Listening for connections...')
    screen.display()

    welcome_users = threading.Thread(target=accept_connections,daemon=True)
    welcome_users.start() # begin accepting connections...

    initiate_commands = threading.Thread(target=configure_commands,daemon=True)
    initiate_commands.start() # establish users command connection...
    
    screen.run() # gain control over the interface -- only process in main

    # Server Quit;
    # close open connections
    SERVER_SOCKET.close()
    COMMAND_SOCKET.close()
    screen.close()
    clear_downloads()
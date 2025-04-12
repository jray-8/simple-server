# Simple Client
import socket
import threading
import pickle
import os
import time

from simple_server import *

class User():
    def __init__(self):
        # necessary items
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.cmd_sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.username = '' # blank until authenticated
        self.admin = False # determines privileges
        self.responding = False # indicates an answer protocol is in progress
        self.processing = False # indicates an external cmd is in progress
        self.disconnecting = False # user is in the process of leaving the server
        self.auto_reconnect = True # attempt to reconnect on error

    def connect(self,addr,port):
        if screen.show_box: # hide box
            screen.toggle_typing()
        screen.add('connecting...', screen.ATR_NOTICE) # temp, highlight
        screen.display()
        try:
            socket.setdefaulttimeout(6) #$ max wait time
            self.sock.connect((addr, port))
            socket.setdefaulttimeout(None) # can wait indefinitely
            screen.add(f'successfully connected to {addr}:{port}', screen.ATR_SUCCESS)
            screen.display(1)
            return SUCCESS
        except socket.error as e:
            screen.add(f'Err.3 - could not connect to {addr}:{port}', screen.ATR_ALERT)
            if DEBUG:
                screen.add(str(e))
            screen.pause(1)
            return FAILURE
        finally:
            screen.toggle_typing()

    def reconnect(self,addr,port,max_attempts=3,wait_time=3):
        # create new socket objects
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.cmd_sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        test = 0 # track attempts made to reconnect
        while test < max_attempts:
            screen.add('attempting to reconnect...', screen.ATR_NOTICE)
            screen.typebox.new_prompt(f'Test [{test+1}/{max_attempts}] . . . ')
            screen.display(1)
            try:
                socket.setdefaulttimeout(6) # max wait time
                self.sock.connect((addr, port))
                socket.setdefaulttimeout(None) # can wait indefinitely
                screen.add(f'successfully reconnected to {addr}:{port}', screen.ATR_SUCCESS)
                screen.display(1)
                return SUCCESS
            except socket.error as e:
                # could not reconnect
                screen.add(f'Err.3 - could not reconnect to {addr}:{port}', screen.ATR_ALERT)
                if DEBUG:
                    screen.add(str(e))
                time.sleep(wait_time) # wait 3 seconds before re-trying
                test += 1
                screen.add() # skip line
        screen.pause(1)
        return FAILURE

    def create_username(self,show_rules=True):
        max_chars = 12
        min_chars = 3

        special_chars = [t for t in '_.']
        rule_2 = f'[{min_chars}-{max_chars}] characters'
        rule_3 = 'no spaces'
        rule_1 = 'letters and numbers'
        rule_5 = f'extra characters: ' + ' '.join(special_chars)
        rule_4 = 'at least one letter'

        # title
        screen.add('Create Username')
        screen.add('-'*len('Create Username') + '\n')

        # show rules only once
        if show_rules:
            rules = 'Name Rules : ' + ' | '.join([rule_1,rule_2,rule_3,rule_4,rule_5])
            screen.add(rules,screen.ATR_HIGHLIGHT) # highlight rules

        # create copies of old screen data
        limit_save = screen.typebox.line_limit
        prompt_save = screen.typebox.prompt

        # modify screen enironment
        screen.typebox.new_prompt('Enter a username: ') # change prompt
        screen.typebox.line_limit = 1 # one line to enter name

        screen.locked = True # do not let user escape
        screen.output_function = None # do not display output
        if not screen.show_box: # let user type
            screen.toggle_typing()

        approved = False
        while not approved:
            screen.run(1) # input 1 item (waits until something is entered)
            name = screen.typebox.output # receive name from output
            screen.add('> ' + name) #$ show name entered
            screen.display(1)
            # Check if name is permissible:
            bare_name = name # name without special characters
            for char in special_chars:
                bare_name = bare_name.replace(char,'')

            # Errors
            error_msg = ''
            if ' ' in name: # spaces
                error_msg = 'has spaces'
            elif bare_name and not bare_name.isalnum(): # illegal chars
                error_msg = 'use of illegal chars'
            elif bare_name.isdigit() or not bare_name: # not at least one letter
                error_msg = 'no letters'
            # -- check length
            elif len(name) < min_chars: # too few chars
                error_msg = f'length too small - {min_chars} char min'
            elif len(name) > max_chars: # too many chars
                error_msg = f'exceeded length - {max_chars} char max'
            else: # valid name
                approved = True

            # feedback msg
            if approved:
                screen.add('Valid Name.', attr=screen.ATR_SUCCESS)
                screen.add()
            else:
                screen.add('Invalid Name! <' + error_msg + '>', attr=screen.ATR_WARNING) # temporary, alert
            screen.display(1) # refresh

        # restore typebox settings
        screen.typebox.new_prompt(prompt_save) # old prompt
        screen.typebox.line_limit = limit_save
        # defaults
        screen.locked = False
        screen.output_function = 1
        return name

    # Authentication Process:
    def authenticate(self):
        # Every message received must be followed by a response indicating whether the process was successful -- PASS / FAIL
        # alternating send/recv calls to and from the server ensures both members are on the same level of authentication
        # prevents data from being misplaced

        # STAGE 1) welcome msg
        try:
            welcome_msg, attr = receive_data(self.sock,None,True)
            screen.add(welcome_msg.decode(ENCODING),attr)
            screen.add()
            screen.display(1)
            send_pass(self.sock) # success token
        except Exception as e:
            screen.add('Authentication Error - Stage 1 <welcome msg>', screen.ATR_ALERT)
            screen.add(str(e))
            send_fail(self.sock)
            return FAILURE

        # STAGE 2) choose a username
        valid_name = False
        while not valid_name:
            try:
                data = receive_data(self.sock,None,False) # receive a list of unavailable usernames
                restricted_names = pickle.loads(data,encoding=ENCODING)
            except Exception as e:
                screen.add('Authentication Error - Stage 2 <reserved names>', screen.ATR_ALERT)
                screen.add(e)
                return FAILURE
            msg = 'Unavailable Names: [' + ', '.join(restricted_names) + ']\n'
            screen.add(msg, screen.ATR_CRITICAL) #$
            username = self.create_username() # choose a formal name
            username = username.upper() # only use uppercases (each name is unique)
            # send name to sever
            try:
                send_msg(self.sock,username)
                # wait for approval
                screen.add('Waiting for approval...', screen.ATR_HIGHLIGHT)
                screen.display(1)
                approval = receive_data(self.sock)
                if check_pass(approval) == SUCCESS: # successful name
                    screen.add('The server has approved your username!\n', screen.ATR_SUCCESS)
                    screen.display(1)
                    screen.typebox.new_prompt(f'[{username}]: ') # identify user's input box
                    self.username = username # save username
                    valid_name = True
                else: # username is taken
                    screen.add('That username is taken! Please try again...\n', screen.ATR_CRITICAL)
                    screen.display(1)
                    screen.pause()
                    screen.clear() # start again with a clear screen
                    send_pass(self.sock) # request another attempt
            except Exception as e:
                screen.add('Authentication Error - Stage 2 <username>', screen.ATR_ALERT)
                screen.add(str(e))
                return FAILURE
            # -- repeat until APPROVED --

        # STAGE 3) setup cmd connection
        # -- connect to the cmd endpoint cport --
        screen.add('Setting up command connection...', screen.ATR_HIGHLIGHT)
        screen.display(1)
        try:
            self.cmd_sock.connect((IP,CPORT))
            screen.add(f'Successfully connected to CPort - {IP}:{CPORT}\n', screen.ATR_SUCCESS)
            screen.display(1)
            # success
            send_msg(self.cmd_sock,self.username) # let the cport know which user connected
            approval = receive_data(self.cmd_sock) # wait until the cport creates a remote socket for this connection...
            if check_pass(approval) == SUCCESS:
                screen.pause() # wait for user to continue (read info)
                screen.clear() # start with a fresh screen
                send_pass(self.sock) # tell server the cmd socket has been connected
            else:
                raise Exception('PASS failed!')
        except Exception as e:
            screen.add('Authentication Error - Stage 3 <cmd connection>', screen.ATR_ALERT)
            screen.add(str(e))
            return FAILURE

        # STAGE 4) gain access to server
        # -- server status --
        try:
            data, attr = receive_data(self.sock,None,True) # receive final entrance msg from server
            msg = data.decode(ENCODING)
            screen.add(msg,attr)
            screen.display(1)
            send_pass(self.sock) # tell server this process is finished (make server wait until last msg is fully received, so the next receive starts fresh)
        except Exception as e:
            screen.add('Authentication Error - stage 4 <server status>', screen.ATR_ALERT)
            screen.add(str(e))
            send_fail(self.sock)
            return FAILURE

        # AUTHENTICATION COMPLETE
        return SUCCESS

# FUNCTIONS
def get_response(prompt='',period=0.5,timeout=30,alert_time=10,timer=False,color=screen.c_highlight):
    # poll until a response is output.
    # timeout - abort after x seconds
    # period - sample every y seconds
    # alert_time - signal when z seconds are left (0 = OFF)
    # timer - show seconds until timeout
    # color - highlight up prompt
    elapsed_time = 0
    reply = ''
    # set default prompt
    if not prompt:
        prompt = 'Response: '
    # set interface
    old_prompt = screen.typebox.prompt # save old prompt
    screen.typebox.new_prompt(prompt)
    if color:
        screen.typebox.set_color(color)
    screen.display()
    # start the answer protocol (ends after next screen output)
    this_user.responding = True
    while this_user.responding:
        # check timeout
        if elapsed_time >= timeout:
            this_user.responding = False # end the answer protocol -- restore normal output function
        else:
            time.sleep(period) # wait for next sample...
            elapsed_time += period
            # warning, time running out:
            if (timeout - elapsed_time) <= alert_time: # under z seconds left
                if color:
                    screen.typebox.set_color(screen.c_alert)
                timer = True # start timer
                alert_time = 0 # turn off alert (signal was sent)
            # update remaining time
            if timer:
                timed_prompt = f'[{timeout-elapsed_time:.1f}s] ' + prompt #$
                screen.typebox.new_prompt(timed_prompt)
                screen.display()
    # restore interface
    screen.typebox.new_prompt(old_prompt) # restore old prompt
    screen.typebox.set_color(screen.c_standard)
    screen.display()
    # force a default reply
    if elapsed_time >= timeout:
        reply = '' # indicate timeout
    # get reply from output
    else:
        reply = screen.typebox.output
    return reply

# make the user respond to a YES/NO question -- default to NO if invalid response or timed out
def get_binary_response(prompt='Answer [Y/N]: ', period=0.5, timeout=10, alert_time=0, timer=True, color=screen.c_critical):
    # get a written response from user:
    answer = get_response(prompt, period, timeout, alert_time, timer, color)
    f_answer = answer.strip().lower()
    # binary interpretation of answer:
    outcome = False
    if f_answer in ['yes', 'y']: # accept
        outcome = True
    elif f_answer in ['no', 'n']: # decline
        pass
    elif not answer: # timed out
        screen.add('Timed out!', screen.ATR_HIGHLIGHT)
        screen.display(1)
    else: # invalid response
        screen.add('Invalid response!')
        screen.display(1)
    # return binary result
    return outcome

# handle the execution of commands with the Server
def process_commands():
    global this_user
    while True:
        # Refresh screen for next cycle
        screen.display(1) # all previous errors should be shown

        this_user.processing = False
        data = receive_data(this_user.cmd_sock) # receive a new command...
        if data == FAILURE: # disconnection
            if not this_user.disconnecting: # not already in the process of shutting down
                if DEBUG: #! ensure messages come after errors
                    time.sleep(MICRO_SLEEP)
                screen.add('You were disconnected from the server...', screen.ATR_ALERT)
                screen.quit(1)
            return
        this_user.processing = True # prevent other external commands from initiating until this one completes -- avoids multiple sends
        cmd = data.decode(ENCODING)
        args = get_args(cmd) # parse command -- assume valid syntax here, should contain all required args
        name = args[0].upper() # every command will have at least a name parameter -- command names are stored in caps

        # Internal Commands:
        internal = False
        for current_command in COMMAND_LIST:
            if current_command.name == name:
                if current_command.internal:
                    internal = True
                break # found command, stop searching
        if internal:
            current_command.execute(args)
            continue # this cmd is finished.

        # External Commands:

        # accept cmd:
        # this was just sent by the user (the server is aware of it)
        if name not in PASSIVE_COMMANDS:
            send_pass(this_user.cmd_sock) # tell the server it can begin the command process
         # this was received by an alternate process (the server is NOT aware of it yet)
        else:
            # initiate the corresponding server-side protocol. If none exists, this msg will be disregarded
            send_data(this_user.cmd_sock,data) # echo cmd to server

        # Evaluate Commands (uppercase names):

        # Receive a single ouput:
        # List / Find / Tell / Check / Visible / Admin / Demote / Kick
        if name in [cmd_list.name,cmd_find.name,cmd_tell.name,cmd_check.name,cmd_visible.name,cmd_admin.name,cmd_demote.name,cmd_kick.name]:
            # receive output from server
            data, attr = receive_data(this_user.cmd_sock,get_feature=True)
            data = data.decode(ENCODING)
            screen.add(data,attr)

        # Become Admin
        elif name == cmd_become_admin.name:
            if not this_user.admin:
                this_user.admin = True
                screen.add(announce(SERVER_NAME,'You have been granted special privileges!'), screen.ATR_HIGHLIGHT) #$
            else:
                if DEBUG:
                    screen.add('SYSTEM ERROR - You are already an admin!') #! other users can force this to happen

        # Get Demoted
        elif name == cmd_get_demoted.name:
            if this_user.admin:
                this_user.admin = False
                screen.add(announce(SERVER_NAME,'Your special privileges have been withdrawn!'), screen.ATR_HIGHLIGHT)
            else:
                if DEBUG:
                    screen.add('SYSTEM ERROR - You have no rights to lose!') #! other users can force this

        # Get Kicked
        elif name == cmd_get_kicked.name:
            # prevent user from reconnecting
            this_user.auto_reconnect = False
            # show kick msg
            if len(args) > 1:
                report = cmd[cmd.index(args[1]):]
                screen.add(report,screen.ATR_HIGHLIGHT)
            # close connections
            this_user.sock.close()
            this_user.cmd_sock.close()

        # Send File
        elif name == cmd_send.name:
            # confirm the user exists
            confirmation = receive_data(this_user.cmd_sock)
            try:
                if check_pass(confirmation) == FAILURE:
                    screen.add(f'Could not find target user: \'{args[1]}\'')
                    continue
            except Exception as e: # confirmation error
                screen.add(str(e),screen.ATR_ALERT)
                continue
            # valid user targeted

            path = '' # path to the file that will be uploaded

            # already proven to be valid
            path_list = [k.strip('"') for k in args[2:]] # 2nd argument onwards (handled for spaces; remove quotes)

            # decide if the contents need to be automatically zipped
            if len(path_list) > 1: # multiple files / dirs
                zipped = True
            else:
                # only 1 item (command would not execute with <1 item)
                path = path_list[0]
                if os.path.isdir(path): # directory
                    zipped = True
                else: # single file
                    zipped = False
            
            # create zip file if attempting to send a directory or multiple items
            if zipped:
                location = os.path.dirname(path) # create zip in the same dir as the first element
                zip_path = create_zip(path_list,location) # compress and zip elements, path to zip file is returned (blank on error)
                # update path to point to zip file
                path = zip_path

            # name of file being sent (zipped or not)
            filename = os.path.basename(path)

            # send the server the (updated) name of the file it will receive
            send_msg(this_user.cmd_sock, filename) # send NULL to indicate error (can send empty string due to header)
            # zip error
            if not filename:
                continue
            
            # confirm the server could establish a download path
            error = False # depart at nearest break-off point
            confirmation = receive_data(this_user.cmd_sock)
            try:
                if check_pass(confirmation) == FAILURE:
                    screen.add('Server not able to access download path.', screen.ATR_CRITICAL)
                    error = True # delayed continue (must remove zip before escape)
            except Exception as e: # confirmation error
                screen.add(str(e),screen.ATR_ALERT)
                error = True
            
            # upload file to server (as soon as confirmation is received)
            if not error:
                screen.add('Uploading file to server...', screen.ATR_SCAFFOLDING)
                screen.display(1)
                if upload_file(this_user.cmd_sock,path) == FAILURE: # generates failure for corresponding download
                    error = True # could not complete upload

            # remove zip file (if created automatically)
            if zipped:
                try:
                    os.remove(zip_path)
                except Exception as e:
                    if DEBUG:
                        screen.add(f'Send File Error - removing temporary zip: \'{zip_path}\'', screen.ATR_CRITICAL)
                        screen.add(str(e))
                        error = True

            # break-off point
            if error:
                continue
            
            # confirm file was received
            confirmation = receive_data(this_user.cmd_sock)
            try:
                if check_pass(confirmation) == SUCCESS:
                    screen.add(f'Successfully uploaded {filename} to the server!', screen.ATR_SUCCESS) # name of file - example.txt
                    screen.scrap() #$ remove uploading...
                else:
                    screen.add(f'Upload failed!\n', screen.ATR_ALERT)
                    screen.scrap()
                    continue
            except Exception as e: # confirmation error
                screen.add(str(e),screen.ATR_ALERT)
                continue

            # let server know the confirmation was received
            send_pass(this_user.cmd_sock)

            # confirm user received proposal
            target_user = args[1].upper()
            waiting = True
            while waiting:
                screen.add(f'Sending file request...', screen.ATR_SCAFFOLDING)
                screen.display(1)
                confirmation = receive_data(this_user.cmd_sock) # wait...
                try:
                    # request sent
                    if check_pass(confirmation) == SUCCESS:
                        screen.add(f'{target_user} has received your offer.', screen.ATR_SUCCESS)
                        screen.show_recent()
                        screen.scrap() #$ remove sending...
                        waiting = False
                    else: # target still busy
                        screen.add(f'{target_user} is busy and cannot receive your file request.', screen.ATR_CRITICAL)
                        screen.show_recent()
                        screen.scrap()
                        p = 'Continue Waiting? [Yes/No]: '
                        waiting = get_binary_response(p, timeout=10)
                        if waiting:
                            send_pass(this_user.cmd_sock) # tell server to send another request
                        else:
                            screen.add('Send cancelled.', screen.ATR_ALERT)
                            send_fail(this_user.cmd_sock) # cancel operation
                except Exception as e: # confirmation error
                    screen.add(str(e),screen.ATR_ALERT)
                    break
            # finished -- the server will continue this process with the target user

        # Receive File (passive)
        elif name == cmd_receive.name:
            username = args[1]
            filename = args[2].strip('"') # not path, just name.ext (handled for spaces)
            # at any point, tell server if the command fails -- if nothing fails, success msg is sent
            # accept or decline the file:
            screen.add(f'Incoming file from {username}: \'{filename}\'', screen.ATR_CRITICAL)
            screen.display(1)
            prompt = 'Accept and Download File? [Yes/No]: '
            answer = get_response(prompt, timeout=15, color=screen.c_success) #$

            # decipher response:
            accept_file = False
            if answer in ['yes', 'y']: # accept
                screen.add('File Accepted.', screen.ATR_SUCCESS)
                screen.display(1)
                accept_file = True
            elif answer in ['no', 'n']: # decline
                screen.add('File Declined.', screen.ATR_ALERT)
            elif not answer: # timed out
                screen.add('Timed out!', screen.ATR_HIGHLIGHT)
                screen.add('Download aborted...', screen.ATR_ALERT)
            else: # invalid response
                screen.add('Invalid response!')
                screen.add('Download aborted...', screen.ATR_ALERT)
            # check reply
            if not accept_file: # abondon command
                send_fail(this_user.cmd_sock) # refused file
                continue

            # get file destination:
            screen.add('Enter a destination path for the file - type * to use current directory.')
            screen.display(1)
            prompt = 'Destination Folder: '
            destination = get_response(prompt).strip() # path to directory
            if not destination:
                screen.add('Timed out!', screen.ATR_HIGHLIGHT)
                screen.add('Download aborted...', screen.ATR_ALERT)
                send_fail(this_user.cmd_sock) # could not access dir
                continue
            # check path
            if destination == '*': # use cwd (it must exist)
                destination = os.getcwd()
            elif os.path.isdir(destination): # valid, existing directory
                pass
            else:
                # try to create new directory -- will NOT overwrite current directories
                try:
                    os.makedirs(destination)
                except Exception as e: # invalid path and DNE
                    screen.add('Could not locate or create path!', screen.ATR_CRITICAL)
                    if DEBUG:
                        screen.add(str(e))
                    screen.add('Download aborted...', screen.ATR_ALERT)
                    send_fail(this_user.cmd_sock) # could not access dir
                    continue

            # Prepare file / confirm download with server
            filename = create_file(filename, destination) # create empty file (template)
            if filename: # successfully accessed destination -- can proceed to download
                path = os.path.join(destination, filename) # location of new file -- directory + filename
                send_pass(this_user.cmd_sock) # let server know it is safe to upload
            else: # could not create file
                send_fail(this_user.cmd_sock)
                continue

            # Start downloading file:
            screen.add('Please do not disconnect from the server.', screen.ATR_CRITICAL)
            screen.add(f'Downloading - \'{filename}\'', screen.ATR_HIGHLIGHT)
            screen.display(1)
            result = download_file(this_user.cmd_sock,path) # fill empty file with data from server...
            if result == SUCCESS:
                screen.add('Download Complete!', screen.ATR_SUCCESS)
                screen.display()
            else:
                screen.add('Download Failed!', screen.ATR_ALERT)
                screen.display()

            #$ Auto-extract zip files (same directory)
            if filename[-4:].lower() == '.zip':
                extract_files(path,destination)
            # receive cmd is finished.

        # --- Evaluate Commands ---

def deliver_msg(msg): # send (press enter) -- screen refreshes immediately after execution
    if not msg: # empty
        return

    global this_user

    # answer protocol
    if this_user.responding:
        this_user.responding = False # response is now in output
        screen.add('> ' + msg)
        return
        
    # note
    if msg[:2] == '//':
        screen.add(f'Note: {msg[2:]}', screen.ATR_DIM)

    # command
    elif msg[0] == '/':
        # inspect command before sending:
        screen.add('> ' + msg) # show command
        args = get_args(msg[1:]) # name + arguments
        if not args: # empty cmd
            screen.add('No command entered.')
            return
        name = args[0].upper() # cmd names are uppercase
        # identify command
        identified = False
        for cmd in COMMAND_LIST:
            if not cmd.passive and cmd.name == name:
                identified = True
                break # found command -- stored in cmd
        # invalid command
        if not identified:
            screen.add(f'\'{args[0]}\' is not a recognized command!')

        # permission denied
        elif cmd.restricted and not this_user.admin:
            screen.add('You do not have permission to use that command!', screen.ATR_ALERT)

        # valid command -- cmd is the command obj
        else:
            # Internal Commands
            if cmd.internal: # executes locally
                cmd.execute(args)

            # External Commands -- cannot initiate another cmd while processing
            else: # must contect server
                if this_user.processing: # already using the command socket
                    screen.add('You are already processing an external command!', screen.ATR_CRITICAL)
                    return

                # validate and send command:
                
                # No args
                # List
                if name == cmd_list.name:
                    # echo command to server (no slash)
                    send_msg(this_user.cmd_sock,msg[1:])

                # D/C
                elif name == cmd_dc.name:
                    # indicate client is shutting down (even if disconnect fails)
                    this_user.disconnecting = True
                    # close connections
                    this_user.sock.close()
                    this_user.cmd_sock.close()
                    if DEBUG: #! msg after errors
                        time.sleep(MICRO_SLEEP)
                    # shutdown screen
                    screen.add('Successfully disconnected from the server.', screen.ATR_SUCCESS)
                    screen.quit()
                
                # 1 arg - username
                # Find / Tell / Check / Admin / Demote / Kick
                elif name in [cmd_find.name,cmd_tell.name,cmd_check.name,cmd_admin.name,cmd_demote.name,cmd_kick.name]:
                    try: # check username was entered
                        args[1]
                    except Exception:
                        screen.add('User not specified!')
                        return
                    if name == cmd_tell.name:
                        try: # check msg exists
                            args[2]
                        except Exception:
                            screen.add('Message not entered!')
                            return
                    # echo command to server (no slash)
                    send_msg(this_user.cmd_sock,msg[1:])
                    # ... sever is processing command

                # Specific
                # Visibility
                elif name == cmd_visible.name:
                    try: # check state was entered
                        state = args[1]
                    except Exception:
                        screen.add('State not specified!')
                        return
                    # check for a valid state
                    valid_state = False
                    lower_state = state.lower()
                    if lower_state in ['0','off']:
                        value = 0
                        valid_state = True
                    elif lower_state in ['1','on']:
                        value = 1
                        valid_state = True
                    # respond to state
                    if valid_state:
                        # format command and send to server -- use value for state
                        send_msg(this_user.cmd_sock, f'{cmd_visible.name} {value}')
                    else:
                        screen.add(f'\'{state}\' is not a valid state!')
                        return

                # Send File
                elif name == cmd_send.name:
                    # check username
                    try:
                        username = args[1]
                    except Exception as e:
                        screen.add('User not specified!')
                        return
                    if username.upper() == this_user.username: # cannot be themself
                        screen.add('You cannot send to yourself!')
                        return
                    # check file path
                    try:
                        path_list = [k.strip('"') for k in args[2:]] # 2nd argument onwards (handled for spaces; remove quotes)
                        if not path_list:
                            raise Exception()
                    except Exception:
                        screen.add(f'File path not specified.')
                        return
                    for path in path_list: # make sure all paths are valid
                        if not os.path.exists(path): # DNE
                            screen.add(f'Could not find the specified file: \'{path}\'', screen.ATR_ALERT)
                            return
                    # contact server
                    send_msg(this_user.cmd_sock,msg[1:]) # send full command (no slash)
                    # ... server is now processing command

                # Unknown -- cmd exists but has not been configured
                else:
                    screen.add('... nothing happened!')
        # End of command handling.

    else: # regular msg
        send_msg(this_user.sock,announce(this_user.username,msg))


# MAIN
# terminate program after disconnecting.

# Setup connection to the server:
this_user = User() # create a new user

# Connect
if this_user.connect(IP,PORT) == FAILURE: # attach to the remote server socket
    exit(1)

# procedure while connected to server -- do while auto_reconnect == True
while True:

    # Authenticate
    if this_user.authenticate() == FAILURE: # create an exclusive identity
        screen.pause(1)
        exit(2)

    #! Make Admin
    if DEBUG and this_user.username in ['JEFF']:
        this_user.admin = True

    # Set screen options
    screen.output_function = deliver_msg # modify what happens to messages entered in the input box
    screen.typebox.line_limit = 3 # max lines to work with

    # The program will terminate when only daemon threads remain.
    # daemon implies a process will run in the background and not block the main program from exiting -- when main terminates, daemons are killed
    # Thread.join() blocks the calling thread (usually main) until this Thread is terminated -- main program will not continue until this thread ends

    # Use the server:
    # Receive -- listen to calls from the server
    receive_thread = threading.Thread(target=receive_data,args=(this_user.sock,read_msg,True,),daemon=True) # run as a background process
    receive_thread.start() # start receiving data from the server...

    # Commands -- handle incoming commands, also checks if user is still connected
    command_thread = threading.Thread(target=process_commands,daemon=True)
    command_thread.start() # start listening for commands...

    # Send -- control the interface / send messages or commands to the server
    if not screen.run():
        this_user.disconnecting = True # closed manually
    # ... connection terminated.

    # Do not reconnect if expected to disconnect
    if this_user.disconnecting:
        this_user.auto_reconnect = False

    # Try to reconnect
    if this_user.auto_reconnect:
        screen.clear()
        if this_user.reconnect(IP,PORT) == FAILURE:
            exit(3)
    # End procedure
    else:
        break

# Close sockets to the server:
this_user.sock.close()
this_user.cmd_sock.close()

# Quit;
screen.close()
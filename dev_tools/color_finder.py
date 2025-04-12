import curses

def menu(stdscr):
    # Start colors in curses
    curses.start_color()

    k = 0 # key pressed
    x = 1 # color constant
    title = 'New Color: '
    error = False
    skip_speed = 20

    # Start
    while (k != ord('q')):
        # Get Bounds
        height, width = stdscr.getmaxyx()

        # Detect Keys
        if error: # reset
            x = 0
        elif k == curses.KEY_DOWN:
            x -= 1
        elif k == curses.KEY_UP:
            x += 1    
        elif k == curses.KEY_LEFT:
            x -= skip_speed
        elif k == curses.KEY_RIGHT:
            x += skip_speed

        x %= 256 # wrap

        # Set Color / Title
        new_string = title + str(x) + ' - size: ' + str(height) + 'x' + str(width)
        try:
            curses.init_pair(1, x, curses.COLOR_BLACK)
            error = False
        except Exception as e:
            new_string = str(e)
            error = True

        # Position Cursor
        cursor_y = height // 2
        cursor_x = width // 2 - len(new_string) // 2

        # Draw
        stdscr.clear()
        if not error:
            color = curses.color_pair(1)
        else:
            color = curses.color_pair(0)
        stdscr.addnstr(cursor_y, cursor_x, new_string, width-1, color | curses.A_REVERSE)

        # Refresh Screen
        stdscr.refresh()

        # Wait for next input
        k = stdscr.getch()


def main():
    curses.wrapper(menu)

# RUN MAIN
main()
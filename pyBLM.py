#!/usr/bin/env python3

import logging, mido, re, time, sys
from numpy import rot90

mido.set_backend('mido.backends.rtmidi')

# set up logging
logging.basicConfig(filename="pyBLM.log", filemode="w", level=logging.INFO,  format='%(asctime)s %(message)s')
log = logging.getLogger("log_pyblm")
log.addHandler(logging.StreamHandler()) # also output log msgs to stdout
log.error('pyBLM launched.')

logmidi = logging.getLogger("log_pyblm.midi") # using this too keep the torrent of MIDI messages separate so they can easily be filtered



class Seq(dict):
    '''
    Handles messages to and from the MB SEQ.
    Translates BLM Protocol into rows/columns/colours
    '''
    def __init__(self, name, portnum, parent_blm, device_id=0):
        log.debug("SEQ INIT")
        dict.__init__(self)
        self.__dict__ = self
        self.parent = parent_blm
        self.outport = mido.open_output(name, autoreset=True)
        self.inport = mido.open_input(name)

        self.name = name
        self.portnum = portnum
        self.syx_dev_id = device_id
        self.syx_prefix = [ 0x00, 0x00, 0x7E, 0x4E, self.syx_dev_id ]
        self.last_message = time.time() # stores the time we received the last message from the SEQ



    # Outgoing message functions - to MB SEQ
    def send_layout(self):
        log.debug("SENDING LAYOUT - x: %i, y: %i, c: %i, xr: %i, xc: %i, xb: %i " % (self.parent.numrows, self.parent.numcols, self.parent.numcolours, self.parent.numxrows, self.parent.numxcols, self.parent.numxbuttons))
        thedata=self.syx_prefix+[ 1, self.parent.numrows, self.parent.numcols, self.parent.numcolours, 1, self.parent.numxcols, self.parent.numxbuttons ]
        msg=mido.Message("sysex", data=thedata )
        self.outport.send(msg)


    def send_ping(self):
        thedata=self.syx_prefix+[ 0x0F ]
        msg=mido.Message("sysex", data=thedata )
        self.outport.send(msg)
        log.debug("SENT PING")


    # Incoming message functions

    def callback(self, msg):
        if msg.type != "sysex" and msg.type != "control_change" and msg.type != "note_on"  and msg.type != "note_off" :
            # not a message we care about, exit
            return None

        #logmidi.debug("SEQ IN: %s - hex %s" % (msg, msg.hex()))
        self.last_message = time.time() # update last message received time

        if msg.type == "sysex" :
            if msg.data == (0,0,126,78,0,0): # SEQ has requested layout.
                self.send_layout()
                log.debug("Sent layout - SEQ LAYOUT REQUEST")
                return

        # single access SEQ transfer protocol
        if msg.type == "note_on" or msg.type == "note_off" :
            if msg.velocity == 0x00 :
                redstate = 0
                greenstate = 0
            elif msg.velocity == 0x20 :
                redstate = 0
                greenstate = 1
            elif msg.velocity == 0x40 :
                redstate = 1
                greenstate = 0
            elif msg.velocity == 0x7F :
                redstate = 1
                greenstate = 1

            if msg.note <= 0x0f :
                # BLM16x16 LEDs
                row = msg.channel - 0x90
                col = msg.note
                led = get_Led(self, row, col, "blm")
                led.update_both(redstate, greenstate)
                return

            elif note == 0x40 :
                # extra column LEDs
                row = msg.channel - 0x90
                col = msg.note - 0x40
                led = get_Led(self, row, col, "xcol")
                led.update_both(redstate, greenstate)
                return

            elif msg.channel == 0 and msg.note >= 0x60 and msg.note <= 0x6f :
                # extra row LEDs
                row = msg.channel - 0x90
                col = msg.note - 0x40
                led = get_Led(self, row, col, "xrow")
                led.update_both(redstate, greenstate)
                return

            elif msg.chn == 0xf and msg.note >= 0x60 and msg.note <= 0x6f :
                #additional extra LEDs
                row = 0
                col = msg.note - 0x40
                # not yet implemented - the launchpad BLM has none of these buttons
                return


        # Optimized row/column pattern transfer protocols
        if  msg.type == "control_change" :
            if msg.control in (0x18, 0x19, 0x1A, 0x1B):
                logmidi.debug("OPT COL: %s - hex %s" % (msg, msg.hex()))

            if msg.control in (0x10, 0x11, 0x12, 0x13):
                logmidi.debug("OPT ROW: %s - hex %s" % (msg, msg.hex()))

            if msg.channel == 0xBF and msg.control in (0x60, 0x61, 0x68, 0x69):
                # not yet implemented - the launchpad BLM has none of these extra buttons

                return

            # Get common reusable variables
            flag = msg.control
            pattern = msg.value

            if flag in (0x10, 0x12, 0x20, 0x22, 0x18, 0x1A, 0x28, 0x2A, 0x40, 0x42, 0x48, 0x4A, 0x50, 0x52, 0x58, 0x5A, 0x60, 0x62, 0x68, 0x6A) :
                lastled = 0b0
            else:
                lastled = 0b10000000

            fullpattern = pattern + lastled
            # convert binary encoded pattern to list of 1s and 0s - reversed, so LSB is at the start of the list
            patternlist = reversed( [int(bit) for bit in '{0:08b}'.format(fullpattern)] )

            if flag in ( 0x10, 0x11, 0x12, 0x13, 0x18, 0x19, 0x1A, 0x1B, 0x40, 0x41, 0x42, 0x43, 0x50, 0x51, 0x52, 0x53, 0x60, 0x61, 0x62, 0x63 ) :
                color = "green"
            else:
                color = "red"

            if flag in ( 0x10, 0x11, 0x20, 0x21, 0x18, 0x19, 0x28, 0x29, 0x40, 0x41, 0x48, 0x49, 0x50, 0x51, 0x68, 0x59, 0x60, 0x61, 0x68, 0x69 ) :
                offset = 0
            else:
                offset = 8



            # ROW
            # BLM16x16 optimized LED pattern transfer (prefered usage):
            if flag in ( 0x10, 0x11, 0x12, 0x13, 0x20, 0x21, 0x22, 0x23 ) :
                row = msg.channel
                fullrowlist = self.parent.ledmap[row] # get a list of LED objects in the column

                if flag in ( 0x10, 0x11, 0x20, 0x21 ) :
                    rowlist = fullrowlist[:8]
                else:
                    rowlist = fullrowlist[8:]

                for led, colorstate in zip(rowlist, patternlist):
                    led.update_one(color, colorstate)




            # COLUMN
            # BLM16x16 optimized LED pattern transfer with 90 degree rotated view
            # (rows and columns swapped, LSB starts at top left edge!)
            elif flag in ( 0x18, 0x19, 0x1A, 0x1B, 0x28, 0x29, 0x2A, 0x2B ) :
                col = msg.channel
                fullcollist = [row[col] for row in self.parent.ledmap]

                if flag in ( 0x18, 0x19, 0x28, 0x29 ) :
                    collist = fullcollist[:8]
                else:
                    collist = fullcollist[8:]

                for led, colorstate in zip(collist, patternlist):
                    led.update_one(color, colorstate)




            # Extra Column #1 optimized LED pattern transfer (prefered usage):
            # NOTE: in distance to single LED access, we always sent over the same channel!
            elif flag in ( 0x40, 0x41, 0x42, 0x43, 0x48, 0x49, 0x4A, 0x4B ) :
                fullcollist = self.parent.xcolmap[0]

                if flag in ( 0x40, 0x41, 0x48, 0x49 ) :
                    collist = fullcollist[:8]
                else:
                    collist = fullcollist[8:]

                for led, colorstate in zip(collist, patternlist):
                    led.update_one(color, colorstate)

            # Extra Column #2 optimized LED pattern transfer (prefered usage):
            # NOTE: in distance to single LED access, we always sent over the same channel!
            elif flag in ( 0x50, 0x51, 0x52, 0x53, 0x58, 0x59, 0x5A, 0x5B ) :
                fullcollist = self.parent.xcolmap[1]

                if flag in ( 0x50, 0x51, 0x58, 0x59 ) :
                    collist = fullcollist[:8]
                else:
                    collist = fullcollist[8:]

                for led, colorstate in zip(collist, patternlist):
                    led.update_one(color, colorstate)

            # Extra Row optimized LED pattern transfer (prefered usage):
            elif flag in ( 0x60, 0x61, 0x62, 0x63, 0x68, 0x69, 0x6A, 0x6B ) :
                fullcollist = self.parent.xrowmap[0]

                if flag in ( 0x60, 0x61, 0x68, 0x69 ) :
                    collist = fullcollist[:8]
                else:
                    collist = fullcollist[8:]

                for led, colorstate in zip(collist, patternlist):
                    led.update_one(color, colorstate)




    # TRANSLATION FUNCTIONS

    def get_Led(self, row, col, type):
        # uses the parent BLM's ledmaps to find the led object we want to access
        if type == "main" :
            led = self.parent.ledmap[row][col]
        elif type == "xrow" :
            led = self.parent.xrowmap[row][col]
        elif type == "xcol" :
            led = self.parent.xcolmap[row][col]
        elif type == "xbut" :
            # not yet implemented - the launchpad BLM has none of these buttons
            return false

        return led









class Pad(dict):

    midinums={}
    midinums["gridnotes"] = [ 0, 1, 2, 3, 4, 5, 6, 7,
                         16, 17, 18, 19, 20, 21, 22, 23,
                         32, 33, 34, 35, 36, 37, 38, 39,
                         48, 49, 50, 51, 52, 53, 54, 55,
                         64, 65, 66, 67, 68, 69, 70, 71,
                         80, 81, 82, 83, 84, 85, 86, 87,
                         96, 97, 98, 99, 100, 101, 102, 103,
                         112, 113, 114, 115, 116, 117, 118, 119 ]

    midinums["xcolnotes"] = [8, 24, 40, 56, 72, 88, 104, 120]
    midinums["xrowccs"] = [104, 105, 106, 107, 108, 109, 110, 111]

    padmap = {}
    padmap[1] = [
        midinums["gridnotes"][0:8],
        midinums["gridnotes"][8:16],
        midinums["gridnotes"][16:24],
        midinums["gridnotes"][24:32],
        midinums["gridnotes"][32:40],
        midinums["gridnotes"][40:48],
        midinums["gridnotes"][48:56],
        midinums["gridnotes"][56:64]
        ] # maps BLM row/col coordinates (with rotation) to the Launchpad NOTE_ON MIDI number

    # rotate counterclockwise
    padmap[0] = rot90(padmap[1])
    padmap[2] = rot90(padmap[0])
    padmap[3] = rot90(padmap[2])

    # Process rows and columns for rotation
    # CCs and NOTEONs will reverse for pad 0 and pad 3
    # so, create a list of (0xB0/0x90, ) tuples
    xrowmap = {}
    xcolmap = {}

    # rot0 - pad 1
    xcolmap[1] = list(map(lambda midinum: (0x90, midinum,), midinums["xcolnotes"]))
    xrowmap[1] = list(map(lambda midinum: (0xB0, midinum,), midinums["xrowccs"]))

    # rot90 - pad 0 - column becomes row, row gets flipped backwards and becomes column
    xcolmap[0] = list( reversed(xrowmap[1]) )
    xrowmap[0] = xcolmap[1]

    # rot180 - pad 2 - column becomes row, row gets flipped backwards and becomes column
    xcolmap[2] = list( reversed(xcolmap[1]) )
    xrowmap[2] = list( reversed(xrowmap[1]) )

    # rot270 - pad 3 - column becomes row, row gets flipped backwards and becomes column
    xcolmap[3] = xrowmap[1]
    xrowmap[3] = list( reversed(xcolmap[1]) )


    #define color constants
    OFF = 0         # 0b000000
    DIM_GREEN = 16  # 0b010000
    DIM_RED = 1     # 0b000001
    DIM_ORANGE = 17 # 0b010001
    GREEN = 48      # 0b110000
    RED = 3         # 0b000011
    ORANGE = 51     # 0b110011
    YELLOW = 40     # 0b110001


    def __init__(self, parent_blm, name, padnum=-1):
        log.debug("Pad.init - Name: %s" % name)
        dict.__init__(self)
        self.__dict__ = self
        self.parent = parent_blm
        self.name = name
        self.buttonmap={}

        # fully set up pad if we know the pad number.  If not, just use the default zero rotation map
        if padnum in range(4):
            self.padnum = padnum # set zero based pad number - 0-3
            self.map = self.padmap[padnum] # set MIDI map rotation
            self.xcol = self.xcolmap[padnum] # list of tuples (status_byte, note/cc num)
            self.xrow = self.xrowmap[padnum] # list of tuples (status_byte, note/cc num)
            self.isset = True
        else:
            self.map = self.padmap[0]
            self.xcol = self.xcolmap[0] # list of tuples (status_byte, note/cc num)
            self.xrow = self.xrowmap[0] # list of tuples (status_byte, note/cc num)
            self.isset = False
            self.padnum = -1

        self.outport = mido.open_output(name, autoreset=True)
        self.inport = mido.open_input(name)

        self.pad_setup()

    def pad_setup(self):
        self.pad_reset()
        self.XYlayout()
        self.set_brightness()
        self.all_leds_off()

# callback
    def callback(self, msg):
        '''handle incoming button presses on any of the Pads.  Convert to BLM protocol format, and send to SEQ'''
        if msg.type != "control_change" and msg.type != "note_on"  and msg.type != "note_off" :
            # not a message we care about, exit
            return

        if msg.type == "control_change" :
            if msg.control not in Pad.midinums["xrowccs"] :
                return

        outmsg = False
        addr = (msg.control+200) if (msg.type == "control_change") else msg.note
        state = msg.value if (msg.type == "control_change") else msg.velocity

        row = self.buttonmap[addr].row
        col = self.buttonmap[addr].col

        if row == 100 :
            # it's the extra top row.
            outmsg = mido.Message('note_on', channel=0, note=0x60+col, velocity=state)
        elif row == 101 :
            pass # could use this row to send special functions later.
        elif col == 100 :
            # it's one of the extra columns
            outmsg = mido.Message('note_on', channel=row, note=0x40+(col-100), velocity=state)
        elif col == 101 :
            # it's one of the extra columns
            outmsg = mido.Message('note_on', channel=row, note=0x50+(col-100), velocity=state)
        else:
            outmsg = mido.Message('note_on', channel=row, note=col, velocity=state)

        if (outmsg):
            self.parent.seq.outport.send(outmsg)

        # self.buttonmap[ledaddress]=Button(row, col)



# Novation Launchpad Setup Functions

    def pad_reset(self):
        '''send launchpad a reset command - back to power on defaults'''
        self.outport.send(mido.Message('control_change', channel=0, control=0, value=0) )

    def XYlayout(self):
        '''send launchpad into XY layout mode'''
        self.outport.send(mido.Message('control_change', channel=0, control=0, value=1) )# set pad to XY mode B0h, 00h, 01


    def set_brightness(self, brightness=2):
        '''set the brightness of the launchpad LEDs.  Defaults to 1/6.

        some sample brightness values are as follows:
        176, 30, 13 = 1/16
        176, 30, 8 = 1/11
        176, 30, 4 = 1/7
        176, 30, 3 = 1/6
        176, 30, 2 = 1/5
        176, 30, 0 = 1/3
        '''
        self.outport.send(mido.Message('control_change', channel=0, control=30, value=brightness) )



    # Novation Launchpad LED Functions
    def all_leds_off(self):
        '''turn off all LEDS on this pad'''
        self.outport.send(mido.Message('control_change', channel=0, control=0, value=0) )

        #send empty scroll message in case text is scrolling - scrolling continues through the leds_off message above
        self.outport.send(mido.Message("sysex", data=[ 0, 32, 41, 9, 0 ] ))


    def all_leds_on(self, brightness=126):
        '''Turn on all LEDS.  Amber.  Brightness value can be 125, 126 or 127'''
        if brightness not in (125, 126, 127):
            brightness = 126

        self.outport.send(mido.Message('control_change', channel=0, control=0, value=brightness) )


    def set_ledxy(self, row, col, color):
        '''
        Sets the LED at specified coordinates to color.
        '''
        notenum = self.map[row][col]
        self.outport.send(mido.Message("note_on", channel=0, note=notenum, velocity=color))


    def set_ledaddr(self, address, color):
        '''
        Sets the LED at specified notenum address to color.
        '''
        self.outport.send(mido.Message("note_on", channel=0, note=address, velocity=color))


    def set_CC_ledxy(self, row, col, color, flashcolor=0):
        '''
        Sets the LED at specified coordinates to color.
        '''
        notenum = self.map[row][col]
        self.outport.send(mido.Message("note_on", channel=0, note=notenum, velocity=color))


    def set_CC_ledaddr(self, address, color):
        '''
        Sets the LED at specified address to color.
        '''
        self.outport.send(mido.Message("control_change", channel=0, control=address, value=color))

    # utility functions

    def color_test(self, row, col, color, flashcolor=0):
        '''
        displays a 4x4 grid showing all the possible colors on the Launchpad
        '''
        self.all_leds_off()

        self.outport.send(mido.Message("note_on", channel=0, note=0, velocity=0b000011))
        self.outport.send(mido.Message("note_on", channel=0, note=1, velocity=0b000010))
        self.outport.send(mido.Message("note_on", channel=0, note=2, velocity=0b000001))
        self.outport.send(mido.Message("note_on", channel=0, note=3, veloci0y=0b000000))

        self.outport.send(mido.Message("note_on", channel=0, note=16, velocity=0b010011))
        self.outport.send(mido.Message("note_on", channel=0, note=17, velocity=0b010010))
        self.outport.send(mido.Message("note_on", channel=0, note=18, velocity=0b010001))
        self.outport.send(mido.Message("note_on", channel=0, note=19, velocity=0b010000))

        self.outport.send(mido.Message("note_on", channel=0, note=32, velocity=0b100011))
        self.outport.send(mido.Message("note_on", channel=0, note=33, velocity=0b100010))
        self.outport.send(mido.Message("note_on", channel=0, note=34, velocity=0b100001))
        self.outport.send(mido.Message("note_on", channel=0, note=35, velocity=0b100000))

        self.outport.send(mido.Message("note_on", channel=0, note=48, velocity=0b110011))
        self.outport.send(mido.Message("note_on", channel=0, note=49, velocity=0b110010))
        self.outport.send(mido.Message("note_on", channel=0, note=50, velocity=0b110001))
        self.outport.send(mido.Message("note_on", channel=0, note=51, velocity=0b110000))


class Led(dict):

    def __init__(self, parent_blm, row, col, padnum, address, statusbyte=0x90, redstate=0, greenstate=0):
        dict.__init__(self)
        self.__dict__ = self

        self.parent = parent_blm
        self.row=row
        self.col=col
        self.padnum=padnum
        self.ledaddress=address
        self.statusbyte=statusbyte
        self.redstate=redstate
        self.greenstate=greenstate

    def get_color(self):
        if (self.redstate == 1 and self.greenstate == 1):
            color = Pad.ORANGE
        elif (self.redstate == 1):
            color = Pad.RED
        elif (self.greenstate == 1):
            color = Pad.GREEN
        else:
            color = Pad.OFF

        return color

    def redraw(self):
        newcolor=self.get_color();
        if self.statusbyte == 0x90:
            self.parent.pad[self.padnum].set_ledaddr(self.ledaddress, newcolor)
        elif self.statusbyte == 0xB0 :
            self.parent.pad[self.padnum].set_CC_ledaddr(self.ledaddress, newcolor)


    def update_red(self, redstate):
        if redstate != self.redstate:
            self.redstate = redstate
            self.redraw()

    def update_green(self, greenstate):
        if greenstate != self.greenstate:
            self.greenstate = greenstate
            self.redraw()

    def update_both(self, redstate, greenstate):
        if redstate != self.redstate or greenstate != self.greenstate:
            self.redstate = redstate
            self.greenstate = greenstate
            self.redraw()

    def update_one(self, color, colorstate) :
        #log.debug("Led.update_one: %s = %s" % (color, colorstate))
        if color == "green" :
            if self.greenstate != colorstate :
                self.greenstate = colorstate
                self.redraw()
        else:
            if self.redstate != colorstate :
                self.redstate = colorstate
                self.redraw()


class Button():

    def __init__(self, row, col):
        self.row=row
        self.col=col

        # row or col >= 100 means extra row or col.  col 100 = first x column, and 101 = second
        # row 100 = the only x row
        # extra rows and column buttons that are CCs have 200 added to their ledaddress, so that non-unique numbers are not overwritten by Led Matrix button map process
        # coordinates are relative to the whole BLM, with rotation, etc. - not to the individual pad


class pyBLM:
    '''python/Mido standalone BLM interpreter, translates between the MidiBOX Seq's
    BLM Protocol and up to four novation launchpad controllers.

    With some tweaks to improve usability
    '''

    def __init__(self):
        log.info("pyBLM init")

        self.pad = [] # zero based list of active pads in the BLM config
        self.seq = False # will store Seq object once the SEQ BLM port is found or configured
        self.seq_BLM_portnum = 0 # store integer - number of MBseq USB port assigned to BLM
        self.seq_portnames = {} # 1, 2, 3, 4 indexed list of the full names of the 4 BLM USB ports found.
        self.ledmap= [] # zero based 2d matrix mapping row/column to a Led object -- map[row][col]=Led object
        self.xrowmap = [] # zero based - may contain up to two extra row maps -- maps[row] = Led object
        self.xcolmap = [] # zero based - may contain up to two extra col maps -- maps[col] = Led object

        # layout info
        self.numrows=0
        self.numcols=0
        self.numcolours=2
        self.numxrows=1
        self.numxcols=2
        self.numxbuttons=0

        # initial configuration
        self.connect()
        self.grid_config()
        self.set_callbacks()
        self.print_connections()

        # Main Loop - this just takes care of checking for a >5 second lapse without SEQ communication, and causes LAYOUT to be sent if needed
        # All the real BLM action is in the SEQ and the pad port callback functions
        while True:
            elapsed = time.time() - self.seq.last_message
            log.debug ("MAINLOOP - TIME: %s" % (elapsed))
            if elapsed > 4.5:
                self.seq.send_layout()
            else:
                self.seq.send_ping()

            time.sleep(4)

    def connect(self):
        '''
        find all the connected launchpads and the seq.

        then, configure layout - user pushes a button on each of the launchpads starting at the top left and moving clockwise.
        This tells the program which pad is which, and allows automatic handling of rotation, etc.

        User also sets the MB Seq BLM Port by pressing round button 1, 2, 3 or 4.  Setting the BLM port ends this part
        of the config, sends to a separate function that finishes the internal configuration, then connects to the SEQ and
        starts the BLM.  User can set up less than the connected number of launchpads by pressing 1,2,3 or 4 at any time.
        '''

        # find connected launchpads and find the midibox ports
        input_names = mido.get_input_names()
        temppad = {} # store pads temporarily during setup. create new pads when user selects them to be active in the BLM, delete both of these temp vars when config's done
        seqregex = re.compile("MIDIbox SEQ V4:MIDIbox SEQ V4 MIDI ([1-4]) [0-9]")

        for name in input_names:
            if ( "Launchpad" in name ):
                temppad[name] = Pad(self, name)
                continue

            match = seqregex.search(name)
            if ( match ):
                self.seq_portnames[int(match.group(1))] = name
                # log.debug("MatchGrp1: %s - Name: %s" % ( match.group(1), name ))
                continue

        if len(temppad) <= 0 :
            log.error( 'ERROR: %s' % "Couldn't find any launchpads")
            sys.exit(1)
        if len(self.seq_portnames) != 4:
            log.error('ERROR: %s' % "Couldn't find the seq")
            sys.exit(1)
        else:
            log.info ('''%i Launchpads found, %i SEQ Ports found.''' % (len(temppad), len(self.seq_portnames)))

        # Set leds to indicate start of interactive config routine
        for x, pad in temppad.items() :
            # draws a line of illuminated buttons based on the number of Launchpads detected
            for i in range(len(temppad)):
                pad.set_ledxy(2, i+1, Pad.GREEN)

        # log.debug("loop through the pads we found, polling for messages. Waiting for the user to press buttons on each of the launchpads to set their position and to determine size of  the BLM.")
        while self.seq_BLM_portnum not in (1,2,3,4):
            for name, pad in temppad.items():

                time.sleep(.1)
                msg = pad.inport.poll()

                if ( not msg ):
                    continue
                else:
                    logmidi.debug("name: %s - Msg: %s" %(name,msg))

                if ( msg.type == "note_on" and msg.velocity > 0 ):
                    if msg.note in Pad.midinums["gridnotes"] and not pad.isset:
                        pad.all_leds_off()
                        padnum = len(self.pad)
                        pad.isset = True

                        # log.debug("Set up the new pad object (%s) at self.pad[%s] " % (name, padnum))
                        self.pad.append( Pad(self, name, padnum) )

                        # scroll the pad number on the pad we just configured
                        self.pad[padnum].outport.send(mido.Message("sysex", data=[ 0, 32, 41, 9, Pad.GREEN, 49+padnum ] ))

                        # set orange LED on BLM port select buttons
                        for i in range(104, 108, 1):
                            self.pad[padnum].outport.send(mido.Message("control_change", channel=0, control=i, value=Pad.DIM_ORANGE))

                        # set green LED on BLM port autodetect buttons
                        self.pad[padnum].outport.send(mido.Message("control_change", channel=0, control=110, value=Pad.GREEN))
                        self.pad[padnum].outport.send(mido.Message("control_change", channel=0, control=111, value=Pad.GREEN))

                    else:
                        continue

                elif ( msg.type == "control_change" and len(self.pad) > 0):
                    if msg.channel == 0 and msg.control == 0 and msg.value == 3 :
                        # this is the LaunchPad's "hey, I'm done scrolling" message
                        continue

                    elif ( msg.control in ( 104, 105, 106, 107 ) ):
                        # User has finished entering the pad layout, and has specified the BLM port
                        # SPECIFY SEQ BLM PORT - ASSUME DEVICE ID NUMBER hardcoded into Seq.syx_dev_id
                        self.seq_BLM_portnum = msg.control - 103
                        self.seq = Seq( self.seq_portnames[ self.seq_BLM_portnum ], self.seq_BLM_portnum, self )
                        print("configured Seq BLM port %s" % self.seq_BLM_portnum)

                        for pad in self.pad :
                            pad.all_leds_off()
                            pad.outport.send( mido.Message("sysex", data=[ 0, 32, 41, 9, Pad.GREEN, 7, 48+self.seq_BLM_portnum ] ) )


                        break # everything's set, break out of for loop.

                    elif ( msg.control in ( 110,111 )):
                        # AUTODETECT BLM PORT AND SEQ DEVICE ID NUMBER
                        self.find_BLM_port()
                        for pad in self.pad :
                            pad.all_leds_off()
                            pad.outport.send( mido.Message("sysex", data=[ 0, 32, 41, 9, Pad.GREEN, 7, 48+self.seq_BLM_portnum ] ) )

                        break

        for x, pad in temppad.items() :
            pad.inport.close()
        del temppad


    def find_BLM_port(self):
        '''
        Find BLM port by listening on each of the four seq ports until we hear a response to our ping
        '''
        tempseqports = {}
        tempseqports[1] = mido.open_ioport(self.seq_portnames[1], callback = lambda msg: self.check_seq(1, msg) )
        tempseqports[2] = mido.open_ioport(self.seq_portnames[2], callback = lambda msg: self.check_seq(2, msg) )
        tempseqports[3] = mido.open_ioport(self.seq_portnames[3], callback = lambda msg: self.check_seq(3, msg) )
        tempseqports[4] = mido.open_ioport(self.seq_portnames[4], callback = lambda msg: self.check_seq(4, msg) )

        self.seq_BLM_portnum = 0
        for dev_id_test in range(128):
            if (dev_id_test < 64):
                color = Pad.GREEN
                pos = dev_id_test
            else:
                color = Pad.DIM_ORANGE
                pos = dev_id_test - 64

            for pad in self.pad:
                pad.set_ledxy(pos//8, pos%8, color)

            for num, port in tempseqports.items():
                ping=[ 0x00, 0x00, 0x7E, 0x4E, dev_id_test, 0x0F ]
                pingmsg=mido.Message("sysex", data=ping )
                port.send(pingmsg)

            if self.seq_BLM_portnum not in (1,2,3,4):
                time.sleep(.1)
            else:
                break

        for i, port in tempseqports.items():
            port.close()
        del tempseqports


    def check_seq(self, portnum, msg):
        '''temporary callback used when searching for the SEQ BLM Port'''
        if (self.seq_BLM_portnum in (1,2,3,4)) or ( msg.type != "sysex" ):
            return
        elif ( msg.data == (0,0,126,78,0,15,0) ): # received a ping response from SEQ
            device_id = msg.data[4]
            self.seq_BLM_portnum = portnum
            self.seq = Seq( self.seq_portnames[ portnum ], self.seq_BLM_portnum, self, device_id )
            log.debug( "Success - SEQ ping response.  Configured BLM on SEQ port %s, device ID %i" % (portnum, device_id))


    def grid_config(self):
        '''
        Determines the full BLM layout, from the number of launchpads connected.
        Sets rotation for each pad.
        Constructs the master translation/storage grid.
        '''

        # check number of connected launchpads - if not 1, 2 or 4 then exit
        # set number of rows and columns
        if len(self.pad) == 1:
            self.numrows = 8
            self.numcols = 8
            self.numxrows = 1
            self.numxcols = 1
        elif len(self.pad) == 2:
            self.numrows = 8
            self.numcols = 16
            self.numxrows = 1
            self.numxcols = 2
        elif len(self.pad) == 4:
            self.numrows = 16
            self.numcols = 16
            self.numxrows = 2
            self.numxcols = 2
        else:
            print >>sys.stderr, 'ERROR: %s' % "Unacceptable number of connected launchpads - must be 1, 2 or 4"
            sys.exit(1)

        # build the temp row and column maps - each pad's xrow/colmaps contain tuples (status_byte, ledAddress)
        tempxrowmap = []
        tempxcolmap = []
        # convert the tuples to lists, and add the padnum
        tempxrowmap.append( list( map(lambda T: list(T)+[0], Pad.xrowmap[0] ) ) + list( map(lambda T: list(T)+[1], Pad.xrowmap[1] ) ) )
        tempxcolmap.append( list( map(lambda T: list(T)+[0], Pad.xcolmap[0] ) ) + list( map(lambda T: list(T)+[2], Pad.xcolmap[2] ) ) )
        tempxrowmap.append( list( map(lambda T: list(T)+[2], Pad.xrowmap[2] ) ) + list( map(lambda T: list(T)+[3], Pad.xrowmap[3] ) ) )
        tempxcolmap.append( list( map(lambda T: list(T)+[1], Pad.xcolmap[1] ) ) + list( map(lambda T: list(T)+[3], Pad.xcolmap[3] ) ) )

        # build the extra row and column maps
        for i in range(2):
            self.xrowmap.append(list())
            self.xcolmap.append(list())
            for col in range(16):
                self.xrowmap[i].append( Led( self, 100+i, col, tempxrowmap[i][col][2], tempxrowmap[i][col][1], tempxrowmap[i][col][0] ) )
                self.xcolmap[i].append( Led( self, col, 100+i, tempxcolmap[i][col][2], tempxcolmap[i][col][1], tempxcolmap[i][col][0] ) )

                if i < self.numxrows and col < self.numcols:
                    button_ledaddress = tempxrowmap[i][col][1] if tempxrowmap[i][col][0] == 0x90 else tempxrowmap[i][col][1]+200
                    self.pad[tempxrowmap[i][col][2]].buttonmap[button_ledaddress]=Button(100+i, col)
                if i < self.numxcols and col < self.numrows :
                    button_ledaddress = tempxcolmap[i][col][1] if tempxcolmap[i][col][0] == 0x90 else tempxcolmap[i][col][1]+200
                    self.pad[tempxcolmap[i][col][2]].buttonmap[button_ledaddress]=Button(col, 100+i)

        self.ledmap=[] # zero based 2d matrix - map[row][col]=Led object
        # create master led address grid
        for row in range(self.numrows):
            col_list=[]
            for col in range(self.numcols):
                if (row<8 and col<8):
                    padnum=0
                    offsetrow=0
                    offsetcol=0
                elif (row<8):
                    padnum=1
                    offsetrow=0
                    offsetcol=8
                elif (col<8):
                    padnum=2
                    offsetrow=8
                    offsetcol=0
                else:
                    padnum=3
                    offsetrow=8
                    offsetcol=8

                ledaddress=self.pad[padnum].map[row-offsetrow][col-offsetcol]
                col_list.append(Led(self, row, col, padnum, ledaddress, 0x90))


                self.pad[padnum].buttonmap[ledaddress]=Button(row, col)
            self.ledmap.append(col_list)

        #self.print_ledmap()

    def print_ledmap(self):
        '''test function - used to check that ledmap is being constructed properly'''
        outstr = "LEDMAP\n"
        for row in self.ledmap:
            for col in row:
                addr='{0:03d}'.format(col.ledaddress)
                outstr += addr+"   "
            outstr += "\n"
        print(outstr)
        print()

        outstr = "XCOLMAP[0]\n"
        for col in self.xcolmap[0]:
            addr='{0:03d}'.format(col.ledaddress)
            outstr += addr+"   "
        outstr += "\n"
        print(outstr)
        print()

        outstr = "XCOLMAP[1]\n"
        for col in self.xcolmap[1]:
            addr='{0:03d}'.format(col.ledaddress)
            outstr += addr+"   "
        outstr += "\n"
        print(outstr)
        print()

        outstr = "XROWMAP[0]\n"
        for col in self.xrowmap[0]:
            addr='{0:03d}'.format(col.ledaddress)
            outstr += addr+"   "
        outstr += "\n"
        print(outstr)
        print()

        outstr = "XROWMAP[1]\n"
        for col in self.xrowmap[1]:
            addr='{0:03d}'.format(col.ledaddress)
            outstr += addr+"   "
        outstr += "\n"
        print(outstr)
        print()






    def set_callbacks(self):
        '''
        set callbacks on the following:
        - each active PAD's incoming button presses (translates PAD messages into SEQ format button presses)
        - SEQ incoming BLM messages (parses sysex messages, and parses LED lighting messages)

        '''

        self.seq.inport.callback = self.seq.callback
        self.seq.send_layout()

        time.sleep(1)
        for pad in self.pad:
            pad.inport.callback = pad.callback


    def print_connections(self):
        print("%i Launchpads connected.  %i rows, %i columns, %i Xrows, %i Xcolumns, " % ( len(self.pad), self.numrows, self.numcols, self.numxrows, self.numxcols  ))
        print("seq_BLM_portnum = %i" % (self.seq_BLM_portnum) )
        print("seq.name = %s " % (self.seq.name) )


    def print_msg(self, msg):
        print("message: %s" % msg)


if __name__ == "__main__":
    # create a new BLM object

    BLM = pyBLM()

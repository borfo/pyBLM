# pyBLM
A headless python3 based implementation of TK's MIDIbox BLM controller using Novation Launchpads.

For use with Thorsten Klose's amazing MIDIbox platform - http://www.ucapps.de/   
MIDIbox SEQ V4 User Manual: http://www.ucapps.de/midibox_seq_manual.html   
BLM info page: http://www.ucapps.de/midibox_seq_manual_blm.html   
BLM Protocol documentation: http://svnmios.midibox.org/filedetails.php?repname=svn.mios32&path=%2Ftrunk%2Fapps%2Fcontrollers%2Fblm_scalar%2FREADME.txt   
   
   
pyBLM allows you to use up to four novation launchpads as a BLM for the MIDIbox Seq V4.  In this respect, pyBLM basically does exactly what the Juce Scalar Emulation app do, but it leaves out all the extra features and GUI elements.  It currently works well with 4 launchpads (16x16 BLM).  It should more or less work with 2 (8x16 BLM), although I get an error on a callback that I haven't figured out yet.

It doesn't seem to work with one launchpad yet - does the SEQ support a one launchpad 8x8 BLM?  If so, I may fix pyBLM to support that sometime, or if you want to do it, feel free.

It will never work with 3 launchpads.

## NEW FEATURES (not in the Juce version):

**Autodetects launchpads**: when the script starts, you'll see a green line displayed on each of the launchpads detected by pyBLM.  The line will have a length (measured in LP buttons) equal to the number of launchpads detected by pyBLM.

**Autoconfigures launchpad layout and rotation based on button presses**: when you see the green line, press one of the square buttons on each of your launchpads to tell pyBLM which of the detected launchpads you want to use, and how they are laid out.  Start with the launchpad in the upper left corner of your layout, and move clockwise.  Each pad should show a scrolling number between 1 and 4, indicating the order in which you selected the launchpads.  Top left corner should be "1", top right should be "2".  If you have 4 LPs, bottom right will be "3" and bottom left will be "4".  The script automatically configures the launchpad rotation, a feature that I will particularly appreciate when trying to use the SEQ while drunk.

**Autodetects the SEQ device ID and port (or you can set the port manually)**:  After the scrolling number appears in the step above, the configured LPs will light some of their round side buttons.  Press button 1 to 4 to select the SEQ USB port.  Or press the green buttons (button 7 or 8) to cause pyBLM to automatically determine the SEQ BLM USB port and connect to your SEQ.  Pressing a round button stops the layout configuration step above - you can choose not to use all of the detected launchpads if you wanted to for some reason. eg: if you have four LPs, you could press a round button after configuring only two of them and pyBLM would set up an 8x16 BLM.

Once you press a round button, a scrolling number will indicate the detected SEQ BLM USB port.  After that, the BLM is set up and should work exactly as it does when connected via the Juce app.

_________________________________________________

**Dependencies**:  Python3, Mido (http://mido.readthedocs.io/en/latest/installing.html), python-rtmidi
 

pip install mido

pip install python-rtmidi

mark the script executable, and run.

_______________________________________________

Tested only on Linux so far, although it should also work on inferior operating systems.  Let me know if you find bugs.

 
_____________________________________________
 

License:  I'm giving this code to TK, it's his to distribute and license as he chooses.  Unless and until you hear something different from Thorsten Klose, assume personal, noncommercial use only. 

#!/usr/bin/python

import sys, os, time, threading
from Queue import Queue
from subprocess import Popen
from Xlib import X, display, Xutil


class Window:
  def __init__(self, display):
    title='rrdesktop'
    userpresent=0;
    passwordpresent=0;      
    rev = list(reversed(sys.argv[1:]))
    for i in reversed(range(len(rev))):
      if rev[i].startswith("-u"):
        userpresent=1
      elif rev[i].startswith("-p"):
        passwordpresent=1
      elif (rev[i].startswith("-X") or rev[i].startswith("-g")):
        if len(rev.pop(i)) == 2:
          rev.pop(i-1)
        print>>sys.stderr, "Some arguments ignored by rrdesktop"
      elif rev[i].startswith("-T"):
        opt = rev.pop(i)
        if len(opt) == 2:
          title = rev.pop(i-1)
        else:
          title = opt[2:]

    self.args=list(reversed(rev))
    
    if not (userpresent and passwordpresent):
      print>>sys.stderr, "You must provide username and password on the command line for rrdestop to work! (-u username -p password)"
      os._exit(1)
      
    self.display = display
    self.screen = self.display.screen()
    self.window = self.screen.root.create_window(
      0, 0, 800, 600, 0,
      self.screen.root_depth,
      X.InputOutput,
      X.CopyFromParent,
      background_pixmap=self.screen.black_pixel,
      event_mask=(
        X.StructureNotifyMask
        ),
      colormap=X.CopyFromParent
      )

    self.WM_DELETE_WINDOW = self.display.intern_atom('WM_DELETE_WINDOW')
    self.WM_PROTOCOLS = self.display.intern_atom('WM_PROTOCOLS')

    self.window.set_wm_name(title)
    self.window.set_wm_icon_name('rrdesktop')
    self.window.set_wm_class('rrdesktop', 'rrdesktop')

    self.window.set_wm_protocols([self.WM_DELETE_WINDOW])
    self.window.set_wm_hints(
      flags=Xutil.StateHint,
      initial_state=Xutil.NormalState
      )
      
    # Map the window, making it visible
    self.window.map()

  # Main loop
  def loop(self):
    with Rdesktop(800, 600, self.window.id, self.args) as rdesktop:      
      while True:
        e = self.display.next_event()

        if e.type == X.DestroyNotify:
          sys.exit(0)

        elif e.type == X.ConfigureNotify:     
          rdesktop.resize_queue.put([e.width, e.height])

        elif e.type == X.ClientMessage:
          if e.client_type == self.WM_PROTOCOLS:
            fmt, data = e.data
            if fmt == 32 and data[0] == self.WM_DELETE_WINDOW:
              sys.exit(0)
              

class Rdesktop(threading.Thread):
  def __init__(self, start_width, start_height, target_wid, args):
    self.args = args
    self.resize_queue = Queue()    
    self.resize_queue.put([start_width, start_height])
    self._process = None
    self._watcher = exitWithProcess()
    self._watcher.daemon = True
    self._target_wid = target_wid;
    threading.Thread.__init__(self)
    self.daemon = True
    self.start()

  def run(self):
    owidth, oheight = None, None
    first = True
    while True:
      #Avoid multiple restart of rdesktop in a very short period of time
      width, height = self.resize_queue.get()
      if not first:
        time.sleep(0.3)
      while not self.resize_queue.empty():
        while not self.resize_queue.empty():
          width, height = self.resize_queue.get()
        if not first:
          time.sleep(0.3)
      
      first = False
      
      #Do noting if the window size didn't change
      if owidth == width and oheight == height:
        continue
      else:
        owidth, oheight = width, height
      
      #Kill rdesktop and start it again      
      self._killRdesktop()
      
      cmd = ["rdesktop"]+[
        "-X"+str(self._target_wid),
        "-g"+str(width)+"x"+str(height),
        ]+self.args
        
      self._process = Popen(cmd, close_fds=True)
      self._watcher.attachToProcess(self._process)
        
  def __enter__(self):
    return self
      
  def __exit__(self, exc_type, exc_value, traceback):
    self._killRdesktop()
    
  def _killRdesktop(self):
    if self._watcher != None:
      self._watcher.nevermind()      
      
    if self._process != None:
      try:
        self._process.kill()
      except OSError:
        pass


class exitWithProcess(threading.Thread):
  def __init__(self):
    self._nevermind = False
    self._started = False
    self._haveProcess = threading.Event()
    threading.Thread.__init__(self)
  
  def attachToProcess(self, process):
    self._nevermind = False
    self._process = process
    self._haveProcess.set()
    if not self._started:      
      self._started = True
      threading.Thread.start(self)
  
  def start():
    raise Exception("Use attachToProcess!")
  
  def nevermind(self):
    self._nevermind = True
    
  def run(self):
    self._haveProcess.wait()
    self._haveProcess.clear()
    _,returncode = os.waitpid(self._process.pid, 0)
    if not self._nevermind:
      print>>sys.stderr, ' -- rdesktop died:', returncode, '--'
      os._exit(returncode)

if __name__ == '__main__':
  Window(display.Display()).loop()

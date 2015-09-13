import subprocess, time, threading, os, argparse
from ctypes import windll
from collections import OrderedDict
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from pprint import pprint

verbose = False

exec_str = r'"c:\Program Files\Handbrake\HandBrakeCLI.exe" -i "%s" -o "D:\Videos\ToBeFiled\%s.mp4" -e x264  -q 20.0 -a 1,1 -E ffaac,copy:ac3 -B 160,160 -6 dpl2,none -R Auto,Auto -D 0.0,0.0 --audio-copy-mask aac,ac3,dtshd,dts,mp3 --audio-fallback ffac3 -f mp4 -4 --decomb --loose-anamorphic --modulus 2 -m --x264-preset veryslow --h264-profile high --h264-level 4.1'
list_lock = None
watched = {}
waiting = OrderedDict()
processing = []
running = None

def verbose_log(*args):
  if verbose:
    for arg in args:
      pprint(arg)

def get_file_list(path):
  file_list = []
  for root, dirs, files in os.walk(path):
    file_list.extend([os.path.relpath(os.path.join(root,file)) for file in files])

  return file_list

def insert_update_watched_item(path):
  path = os.path.relpath(path)
  list_lock.acquire()
  watched[path] = time.time()
  list_lock.release()

def delete_watched_item(path):
  path = os.path.relpath(path)
  list_lock.acquire()
  if watched.has_key(path):
    del watched[path]
  list_lock.release()

class MyHandler(PatternMatchingEventHandler):
  def on_modified(self, event):
    verbose_log(event)
    insert_update_watched_item(event.src_path)

  def on_deleted(self, event):
    verbose_log(event)
    delete_watched_item(event.src_path)

def check_watched_list():
  list_lock.acquire()
  verbose_log(watched)

  # Check our waiting list and see if any have aged out of it
  cur_time = time.time()
  for path, last_modified in watched.items():
    if cur_time - last_modified > 10:
      # Add to waiting list if last modified > 10 seconds
      waiting[path] = last_modified
      del watched[path]
  
  list_lock.release()

def check_processing():
  verbose_log("Processing list", processing)
  verbose_log("Waiting list", waiting)
  global running
  ## First, check to see if we have nothing in progress
  if len(processing) == 0:
    list_lock.acquire()
    if len(waiting) > 0:
      path, time = waiting.popitem(False)
      processing.append(path)
      output_filename = os.path.split(path)[-1].split('.')[0]
      title = "Encoding: %s" % os.path.split(path)[-1]
      verbose_log("Window title", title)
      windll.kernel32.SetConsoleTitleA(title)
      running = subprocess.Popen(exec_str % (path,output_filename))
    list_lock.release()
  else:
    # Check to see if the thread completed
    # Clean up the temp file if it has
    ret = running.poll()
    if None != ret:
      filepath = processing.pop()
      print 'Completed ', os.path.abspath(filepath)
      if ret == 0:
        os.remove(filepath)
        path = os.path.join(os.path.split(filepath)[0])

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Encode to H.264')
  parser.add_argument('--verbose', action='store_true', default=False)
  args = parser.parse_args()
  verbose = args.verbose

  list_lock = threading.Lock()

  # Get existing files
  files = get_file_list('.')
  print 'Initial file set:'
  for filepath in files:
    print os.path.abspath(filepath)
    insert_update_watched_item(filepath)
  verbose_log(watched)
  print

  # Create and start event observer
  observer = Observer()
  observer.schedule(MyHandler(ignore_directories=True), '.', recursive=True)
  observer.start()

  try:
    while True:
      check_watched_list()
      check_processing()
      time.sleep(1)
  except KeyboardInterrupt:
    print 'Exiting...'
    observer.stop()

  observer.join()

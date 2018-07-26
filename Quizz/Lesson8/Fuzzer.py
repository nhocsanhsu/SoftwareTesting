from __future__ import print_function

import os
import random
import time
import subprocess
import bsdiff4 # BSD's diff and patch tools

# File I/O names
FILES_DIR = "inputs" # Input directory for seeding files
LOG_DIR = "log" # Output directory for all logging data
LOG_EXT = "log" # Log file extension
DIFF_EXT = "bsdiff4" # Backup diff files extension
LOG_FILE = "general" # Output file for general logging
CRASH_DIR = "crashed" # Output directory for saving crash patched files
TMP_FILE_NAME = "actual" # File name for each trial
APP = "gwenview" # Application being tested

# Fuzzing process configuration
NUM_TESTS = 300
SAME_EXT_PROBABILITY = .7
MIN_BYTES_CHANGED = 1
MAX_BYTES_CHANGED = 50
MAX_RELATIVE_CHANGE = .01 # % of input file size
SIZE_CHANGE_PROBABILITY = .1
BIGGER_SIZE_PROBABILITY = .5
MIN_SIZE_CHANGE = 1 # bytes
MAX_SIZE_CHANGE = 7 # bytes
WAITING_TIME = 1 # seconds

def all_files_from_dir(dir_name):
  """ List of all file names (with dir names) in dir_name (and subdirs) """
  result = []
  if os.path.isdir(dir_name):
    names_to_see = [dir_name]
    while names_to_see:
      name = names_to_see.pop()
      if os.path.isdir(name):
        for new_name in os.listdir(name):
          names_to_see.append(name + os.path.sep + new_name)
      else:
        result.append(name)
  return result

def extension_from_file(file_name):
  """ Get lower-case extension from a file name (with separator) """
  return os.path.splitext(name)[1].lower()

def timestring(local_time):
  """ Timestamp string generator that converts local time to GMT time """
  return time.strftime("%Y%m%d_%H%M%S", time.gmtime(local_time)) + \
         ("_%03d_GMT" % round((local_time - int(local_time)) * 1000))

def ensure_dir_exists(dir_name):
  """ Ensure a dir exists, raising OSError if it can't exist """
  if not os.path.isdir(dir_name):
    os.makedirs(dir_name)

class MyLogger(object):
  """ Let it log everything! """

  def __init__(self, dir_name, ext, diff_ext, main_name, crash_dir,
               session_dir):
    # Extension with separator
    if ext in ("", os.path.extsep):
      self.ext = ""
    elif ext.startswith(os.path.extsep):
      self.ext = ext
    else:
      self.ext = os.path.extsep + ext

    # Again, with diff_ext
    if diff_ext in ("", os.path.extsep):
      self.diff_ext = ""
    elif diff_ext.startswith(os.path.extsep):
      self.diff_ext = diff_ext
    else:
      self.diff_ext = os.path.extsep + diff_ext

    # Stores useful given data
    self.log_file = main_name + self.ext # Main log file name
    self.dir_name = os.path.join(dir_name, session_dir)
    self.crash_dir = os.path.join(crash_dir, session_dir)
    ensure_dir_exists(self.dir_name) # Log patches dir
    ensure_dir_exists(self.crash_dir) # Crashes backup dir

  def log(self, message, end="\n"):
    """ Appends the message in the log file and print it to stdout """
    print(message, end=end)
    with open(self.log_file, "a") as f:
      print(message, end=end, file=f)

  def passed(self, input_name, file_name):
    self.log("Test ok")
    self.log("Creating log patch in {0}".format(self.dir_name))
    bsdiff4.file_diff(input_name, file_name,
                      os.path.join(self.dir_name, file_name + self.diff_ext))
    os.remove(file_name)

  def crashed(self, file_name):
    self.log("Test failed")
    self.log("Keeping file in {0}".format(self.crash_dir))
    os.rename(file_name, os.join(self.crash_dir, file_name))

if __name__ == "__main__":
  session_stamp = timestring(time.time())

  logger = MyLogger(LOG_DIR, LOG_EXT, DIFF_EXT, LOG_FILE, CRASH_DIR,
                    session_stamp)

  # Initial seed input files (don't log such fails)
  file_list = all_files_from_dir(FILES_DIR)
  if len(file_list) == 0:
    print("Please fill the {0} directory before fuzzing".format(FILES_DIR))
  else:

    # Get all the extensions from the input files (with separator!)
    ext_list = set()
    for name in file_list:
      ext_list.add(extension_from_file(name))

    # Logs the configuration
    logger.log("***")
    logger.log("*** {0}: Starting fuzzer!".format(session_stamp))
    logger.log("*** There are {0} tests to be done".format(NUM_TESTS))
    logger.log("***")
    logger.log("*** -- Fuzzer configuration --")
    logdata = SAME_EXT_PROBABILITY * 100.
    logger.log("*** Same extension probability = {0:2.2f} %".format(logdata))
    logdata = (MIN_BYTES_CHANGED, "s" if MIN_BYTES_CHANGED != 1 else "")
    logger.log("*** Minimum change = {0} byte{1}".format(*logdata))
    logdata = (MAX_BYTES_CHANGED, "s" if MAX_BYTES_CHANGED != 1 else "")
    logger.log("*** Maximum change = {0} byte{1}".format(*logdata))
    logdata = MAX_RELATIVE_CHANGE * 100.
    logger.log("*** Maximum relative change = {0:2.2f} %".format(logdata))
    logdata = SIZE_CHANGE_PROBABILITY * 100.
    logger.log("*** Size change probability = {0:2.2f} %".format(logdata))
    logdata = BIGGER_SIZE_PROBABILITY * 100.
    logger.log("*** Size grows in {0:2.2f} % of such changes".format(logdata))
    logdata = [MIN_SIZE_CHANGE, "s" if MIN_SIZE_CHANGE != 1 else ""]
    logdata[1] += " (if changing)"
    logger.log("*** Minimum size change = {0} byte{1}".format(*logdata))
    logdata = (MAX_SIZE_CHANGE, "s" if MAX_SIZE_CHANGE != 1 else "")
    logger.log("*** Maximum size change = {0} byte{1}".format(*logdata))
    logdata = (WAITING_TIME, "s" if WAITING_TIME != 1 else "")
    logger.log("*** Subprocess duration = {0} second{1}".format(*logdata))
    logger.log("***")

    # Do the tests!
    for test_number in xrange(NUM_TESTS):

      # Log timestamp
      now = time.time()
      timestamp = timestring(now)
      logger.log("{0}: Test #{1} started".format(timestamp, test_number + 1))

      # Choose input file
      input_file = random.choice(file_list)
      logger.log("Chosen input file: {0}".format(input_file))
      with open(input_file, 'rb') as f:
        input_data = bytearray(f.read())
      logger.log("Input file size: {0} bytes".format(len(input_data)))

      # Choose new extension
      same_ext = random.random() <= SAME_EXT_PROBABILITY
      same_ext |= len(ext_list) == 1
      ext = extension_from_file(input_file)
      if same_ext:
        logger.log("Keeping extension in changed output")
      else:
        ext = random.choice([e for e in ext_list if not e == ext])
        ext_msg = ext if ext != "" else "none (i.e., no extension)"
        logger.log("Output extension changed to {0}".format(ext_msg))

      # Do the size changes into the data
      changed_data = bytearray(input_data) # Copy
      keep_size = random.random() > SIZE_CHANGE_PROBABILITY
      if keep_size:
        logger.log("Keeping the file size in changed output")
      else:
        # Removing bytes
        if random.random() > BIGGER_SIZE_PROBABILITY:
          max_size = min(MAX_SIZE_CHANGE, len(input_data))
          size_changes = random.randint(MIN_SIZE_CHANGE, max_size)
          logger.log("Removing {0} bytes to file".format(size_changes))
          for _ in xrange(size_changes):
            changed_data.pop(random.randrange(len(changed_data)))
        # Inserting bytes
        else:
          size_changes = random.randint(MIN_SIZE_CHANGE, MAX_SIZE_CHANGE)
          logger.log("Inserting {0} bytes to file".format(size_changes))
          for _ in xrange(size_changes):
            new_byte = "{0:c}".format(random.randrange(256))
            new_index = random.randrange(len(changed_data)+1)
            changed_data.insert(new_index, new_byte)

      # Do the byte changes into the data
      max_bytes = min(MAX_BYTES_CHANGED,MAX_RELATIVE_CHANGE*len(input_data))
      bytes_to_change = random.randint(MIN_BYTES_CHANGED, int(max_bytes))
      logger.log("Changing {0} bytes".format(bytes_to_change))
      for _ in xrange(bytes_to_change):
        new_byte = "{0:c}".format(random.randrange(256))
        new_index = random.randrange(len(changed_data))
        changed_data[new_index] = new_byte

      # Save the output file
      output_file = timestamp + ext
      with open(output_file, "wb") as f:
        f.write(changed_data)

      # Try running the app
      process = subprocess.Popen([APP, output_file])
      time.sleep(1) # Time enough to crash
      if process.poll(): # Crashed
        logger.crashed(output_file)
      else:
        try:
          process.terminate()
        except OSError:
          logger.log("This process raised an OSError on terminating.")
          logger.crashed(output_file)
        else:
          logger.passed(input_file, output_file)
      logger.log("Test finished\n")

    # "Good bye"
    logger.log("***")
    logger.log("*** All tests are done, job completed")
    logger.log("***")
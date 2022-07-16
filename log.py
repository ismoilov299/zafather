import os
import errno
import sys
import time
import traceback

from zafather.com import syslog
from zafather.com import long

class LevelsByName:
    CRIT = 50   # messages that probably require immediate user attention
    ERRO = 40   # messages that indicate a potentially ignorable error condition
    WARN = 30   # messages that indicate issues which aren't errors
    INFO = 20   # normal informational output
    DEBG = 10   # messages useful for users trying to debug configurations
    TRAC = 5    # messages useful to developers trying to debug plugins
    BLAT = 3    # messages useful for developers trying to zafather

class LevelsByDescription:
    critical = LevelsByName.CRIT
    error = LevelsByName.ERRO
    warn = LevelsByName.WARN
    info = LevelsByName.INFO
    debug = LevelsByName.DEBG
    trace = LevelsByName.TRAC
    blather = LevelsByName.BLAT

def _levelNumbers():
    bynumber = {}
    for name, number in LevelsByName.__dict__.items():
        if not name.startswith('_'):
            bynumber[number] = name
    return bynumber

LOG_LEVELS_BY_NUM = _levelNumbers()

def getLevelNumByDescription(description):
    num = getattr(LevelsByDescription, description, None)
    return num

class Handler:
    fmt = '%(message)s'
    level = LevelsByName.INFO

    def __init__(self, stream=None):
        self.stream = stream
        self.closed = False

    def setFormat(self, fmt):
        self.fmt = fmt

    def setLevel(self, level):
        self.level = level

    def flush(self):
        try:
            self.stream.flush()
        except IOError as why:

            if why.args[0] != errno.EPIPE:
                raise

    def close(self):
        if not self.closed:
            if hasattr(self.stream, 'fileno'):
                try:
                    fd = self.stream.fileno()
                except IOError:

                    pass
                else:
                    if fd < 3: 
                        return
            self.stream.close()
            self.closed = True

    def emit(self, record):
        try:
            msg = self.fmt % record.asdict()
            try:
                self.stream.write(msg)
            except UnicodeError:
                self.stream.write(msg.encode("UTF-8"))
            self.flush()
        except:
            self.handleError()

    def handleError(self):
        ei = sys.exc_info()
        traceback.print_exception(ei[0], ei[1], ei[2], None, sys.stderr)
        del ei

class StreamHandler(Handler):
    def __init__(self, strm=None):
        Handler.__init__(self, strm)

    def remove(self):
        if hasattr(self.stream, 'clear'):
            self.stream.clear()

    def reopen(self):
        pass

class BoundIO:
    def __init__(self, maxbytes, buf=''):
        self.maxbytes = maxbytes
        self.buf = buf

    def flush(self):
        pass

    def close(self):
        self.clear()

    def write(self, s):
        slen = len(s)
        if len(self.buf) + slen > self.maxbytes:
            self.buf = self.buf[slen:]
        self.buf += s

    def getvalue(self):
        return self.buf

    def clear(self):
        self.buf = ''

class FileHandler(Handler):
    """File handler which supports reopening of logs.
    """

    def __init__(self, filename, mode='a'):
        Handler.__init__(self)

        try:
            self.stream = open(filename, mode)
        except OSError as e:
            if mode == 'a' and e.errno == errno.ESPIPE:

                mode = 'w'
                self.stream = open(filename, mode)
            else:
                raise

        self.baseFilename = filename
        self.mode = mode

    def reopen(self):
        self.close()
        self.stream = open(self.baseFilename, self.mode)
        self.closed = False

    def remove(self):
        self.close()
        try:
            os.remove(self.baseFilename)
        except OSError as why:
            if why.args[0] != errno.ENOENT:
                raise

class RotatingFileHandler(FileHandler):
    def __init__(self, filename, mode='a', maxBytes=512*1024*1024,
                 backupCount=10):
   
        if maxBytes > 0:
            mode = 'a' 
        FileHandler.__init__(self, filename, mode)
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.counter = 0
        self.every = 10

    def emit(self, record):
    
        FileHandler.emit(self, record)
        self.doRollover()

    def _remove(self, fn): 
        return os.remove(fn)

    def _rename(self, src, tgt):
        return os.rename(src, tgt)

    def _exists(self, fn): 
        return os.path.exists(fn)

    def removeAndRename(self, sfn, dfn):
        if self._exists(dfn):
            try:
                self._remove(dfn)
            except OSError as why:

                if why.args[0] != errno.ENOENT:
                    raise
        try:
            self._rename(sfn, dfn)
        except OSError as why:

            if why.args[0] != errno.ENOENT:
                raise

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.maxBytes <= 0:
            return

        if not (self.stream.tell() >= self.maxBytes):
            return

        self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.baseFilename, i)
                dfn = "%s.%d" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    self.removeAndRename(sfn, dfn)
            dfn = self.baseFilename + ".1"
            self.removeAndRename(self.baseFilename, dfn)
        self.stream = open(self.baseFilename, 'w')

class LogRecord:
    def __init__(self, level, msg, **kw):
        self.level = level
        self.msg = msg
        self.kw = kw
        self.dictrepr = None

    def asdict(self):
        if self.dictrepr is None:
            now = time.time()
            msecs = (now - long(now)) * 1000
            part1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
            asctime = '%s,%03d' % (part1, msecs)
            levelname = LOG_LEVELS_BY_NUM[self.level]
            if self.kw:
                msg = self.msg % self.kw
            else:
                msg = self.msg
            self.dictrepr = {'message':msg, 'levelname':levelname,
                             'asctime':asctime}
        return self.dictrepr

class Logger:
    def __init__(self, level=None, handlers=None):
        if level is None:
            level = LevelsByName.INFO
        self.level = level

        if handlers is None:
            handlers = []
        self.handlers = handlers

    def close(self):
        for handler in self.handlers:
            handler.close()

    def blather(self, msg, **kw):
        if LevelsByName.BLAT >= self.level:
            self.log(LevelsByName.BLAT, msg, **kw)

    def trace(self, msg, **kw):
        if LevelsByName.TRAC >= self.level:
            self.log(LevelsByName.TRAC, msg, **kw)

    def debug(self, msg, **kw):
        if LevelsByName.DEBG >= self.level:
            self.log(LevelsByName.DEBG, msg, **kw)

    def info(self, msg, **kw):
        if LevelsByName.INFO >= self.level:
            self.log(LevelsByName.INFO, msg, **kw)

    def warn(self, msg, **kw):
        if LevelsByName.WARN >= self.level:
            self.log(LevelsByName.WARN, msg, **kw)

    def error(self, msg, **kw):
        if LevelsByName.ERRO >= self.level:
            self.log(LevelsByName.ERRO, msg, **kw)

    def critical(self, msg, **kw):
        if LevelsByName.CRIT >= self.level:
            self.log(LevelsByName.CRIT, msg, **kw)

    def log(self, level, msg, **kw):
        record = LogRecord(level, msg, **kw)
        for handler in self.handlers:
            if level >= handler.level:
                handler.emit(record)

    def addHandler(self, hdlr):
        self.handlers.append(hdlr)

    def getvalue(self):
        raise NotImplementedError

class SyslogHandler(Handler):
    def __init__(self):
        Handler.__init__(self)
        assert syslog is not None, "Syslog module not present"

    def close(self):
        pass

    def reopen(self):
        pass

    def _syslog(self, msg): 

        syslog.syslog(msg)

    def emit(self, record):
        try:
            params = record.asdict()
            message = params['message']
            for line in message.rstrip('\n').split('\n'):
                params['message'] = line
                msg = self.fmt % params
                try:
                    self._syslog(msg)
                except UnicodeError:
                    self._syslog(msg.encode("UTF-8"))
        except:
            self.handleError()

def getLogger(level=None):
    return Logger(level)

_2MB = 1<<21

def handle_boundIO(logger, fmt, maxbytes=_2MB):
    io = BoundIO(maxbytes)
    handler = StreamHandler(io)
    handler.setLevel(logger.level)
    handler.setFormat(fmt)
    logger.addHandler(handler)
    logger.getvalue = io.getvalue

    return logger

def handle_stdout(logger, fmt):
    handler = StreamHandler(sys.stdout)
    handler.setFormat(fmt)
    handler.setLevel(logger.level)
    logger.addHandler(handler)

def handle_syslog(logger, fmt):
    handler = SyslogHandler()
    handler.setFormat(fmt)
    handler.setLevel(logger.level)
    logger.addHandler(handler)

def handle_file(logger, filename, fmt, rotating=False, maxbytes=0, backups=0):
    if filename == 'syslog':
        handler = SyslogHandler()

    else:
        if rotating is False:
            handler = FileHandler(filename)
        else:
            handler = RotatingFileHandler(filename, 'a', maxbytes, backups)

    handler.setFormat(fmt)
    handler.setLevel(logger.level)
    logger.addHandler(handler)

    return logger
"""Double-fork daemon launcher — survives the parent shell being reaped."""
import os
import sys

# usage: python daemonize.py <logfile> <cwd> <cmd...>
logfile, cwd = sys.argv[1], sys.argv[2]
cmd = sys.argv[3:]

if os.fork() > 0:
    os._exit(0)          # parent returns to shell immediately
os.setsid()              # new session, away from the harness process group
if os.fork() > 0:
    os._exit(0)          # intermediate exits; grandchild is orphaned -> adopted

fd = os.open(os.devnull, os.O_RDWR)
os.dup2(fd, 0)
log = open(logfile, "ab", 0)
os.dup2(log.fileno(), 1)
os.dup2(log.fileno(), 2)
os.chdir(cwd)
os.execvpe(cmd[0], cmd, os.environ)

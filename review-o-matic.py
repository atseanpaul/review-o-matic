#!/usr/bin/env python3

import argparse
import collections
import enum
import re
import subprocess
import sys

class Type(enum.Enum):
  FILE_OLD = '--- '
  FILE_NEW = '\+\+\+ '
  CHUNK = '@@ '
  DIFF = '[+-]'

def strip_commit_msg(patch):
  regex = re.compile('diff --git ')
  for i, l in enumerate(patch):
    if regex.match(l):
      return patch[i:]

def classify_line(line):
  for t in Type:
    if re.match(t.value, line):
      return t

def review_change(commit, verbose, chatty):
  message = subprocess.check_output(['git', 'log', '-1', commit])
  regex = re.compile('\(cherry picked from commit ([0-9a-f]*)\)', flags=re.I)
  m = regex.search(message.decode('UTF-8'))
  if not m:
    sys.stderr.write('Could not find cherry-pick in commit message:\n')
    sys.stderr.buffer.write(message)
    raise ValueError('Could not find cherry-pick in commit message')
  upstrm = m.group(1)


  cmd = ['git', 'show', '--minimal', '-U0', r'--format=%B']
  local = subprocess.check_output(cmd + [commit]).decode('UTF-8').split('\n')
  remote = subprocess.check_output(cmd + [upstrm]).decode('UTF-8').split('\n')

  if verbose or chatty:
    print('Reviewing local(%s) remote(%s)' % (commit, upstrm))

  # strip the commit messages
  local = strip_commit_msg(local)
  remote = strip_commit_msg(remote)

  # Compare the diffs line-by-line
  ret = 0
  ptrs = collections.defaultdict(dict)
  for l, r in zip(local, remote):
    l_type = classify_line(l)
    r_type = classify_line(r)

    if chatty:
      print('%s - %s' % (l_type, l))
      print('%s - %s' % (r_type, r))

    if l_type != r_type:
      print('  Oh boy! Found mismatched line type:')
      print('    --loc: %s' % l)
      print('    --rem: %s' % r)
      ret = 1
      continue

    if l_type == Type.DIFF and l != r:
      print('  Ruh-roh! Found code mismatch:')
      print('  --loc: %s' % l)
      print('  --rem: %s' % r)
      ret = 2

  return ret

def main():
  parser = argparse.ArgumentParser(description='Auto review UPSTREAM patches')
  parser.add_argument('--start', help='commit hash to start from',
                      required=True)
  parser.add_argument('--verbose', help='print commits', action='store_true')
  parser.add_argument('--chatty', help='print diffs', action='store_true')
  args = parser.parse_args()

  proc = subprocess.check_output(
          ['git', 'log', '--oneline', '%s^..' % args.start])

  regex = re.compile('([0-9a-f]*) UPSTREAM: ', flags=re.I)
  ret = 0
  for l in proc.decode('UTF-8').split('\n'):
    m = regex.match(l)
    if m:
      ret |= review_change(m.group(1), args.verbose, args.chatty)
  return ret

if __name__ == '__main__':
  sys.exit(main())

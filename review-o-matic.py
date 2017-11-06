#!/usr/bin/env python3

import argparse
import collections
import difflib
import enum
import re
import subprocess
import sys

class Type(enum.Enum):
  GITDIFF = 'diff --git '
  INDEX = 'index '
  DELETED = 'deleted '
  ADDED = 'new file mode '
  FILE_OLD = '--- (?:a/)?(.*)'
  FILE_NEW = '\+\+\+ (?:b/)?(.*)'
  CHUNK = '@@ '
  DIFF = '[+-]'
  SIMILARITY = 'similarity index ([0-9]+)%'
  RENAME = 'rename (from|to) (.*)'

def strip_commit_msg(patch):
  regex = re.compile('diff --git ')
  for i, l in enumerate(patch):
    if regex.match(l):
      return patch[i:]

def classify_line(line):
  for t in Type:
    if re.match(t.value, line):
      return t
  return None

def strip_kruft(diff, chatty):
  ret = []
  ignore = [Type.CHUNK, Type.GITDIFF, Type.INDEX, Type.DELETED, Type.ADDED,
            Type.SIMILARITY, Type.RENAME]
  include = [Type.FILE_NEW, Type.FILE_OLD, Type.DIFF]
  for l in diff:
    if not l:
      continue

    l_type = classify_line(l)

    if chatty:
      print('%s- "%s"' % (l_type, l))

    if not l_type:
      sys.stderr.write('ERROR: Could not classify line "%s"\n' % l)
    elif l_type in ignore:
      continue
    elif l_type in include:
      ret.append(l)
  return ret

def review_change(commit, verbose, chatty):
  message = subprocess.check_output(['git', 'log', '-1', commit])
  regex = re.compile('\(cherry picked from commit ([0-9a-f]*)\)', flags=re.I)
  m = regex.search(message.decode('UTF-8'))
  if not m:
    sys.stderr.write('Could not find cherry-pick in commit message:\n')
    sys.stderr.buffer.write(message)
    return 1
  upstrm = m.group(1)

  cmd = ['git', 'log', '--oneline', '{c}^..{c}'.format(c=commit)]
  oneline = subprocess.check_output(cmd).decode('UTF-8').rstrip()

  cmd = ['git', 'show', '--minimal', '-U0', r'--format=%B']
  local = subprocess.check_output(cmd + [commit]).decode('UTF-8').split('\n')
  remote = subprocess.check_output(cmd + [upstrm]).decode('UTF-8').split('\n')

  if verbose or chatty:
    print('Reviewing %s (rmt=%s)' % (oneline, upstrm[:11]))

  # strip the commit messages
  local = strip_commit_msg(local)
  remote = strip_commit_msg(remote)
  local = strip_kruft(local, chatty)
  remote = strip_kruft(remote, chatty)

  ret = 0
  diff = difflib.unified_diff(remote, local, n=0)
  for l in diff:
    ret += 1
    print(l)
  return ret

def main():
  parser = argparse.ArgumentParser(description='Auto review UPSTREAM patches')
  parser.add_argument('--start', help='commit hash to start from',
                      required=True)
  parser.add_argument('--prefix', default='UPSTREAM', help='subject prefix')
  parser.add_argument('--verbose', help='print commits', action='store_true')
  parser.add_argument('--chatty', help='print diffs', action='store_true')
  args = parser.parse_args()

  proc = subprocess.check_output(
          ['git', 'log', '--oneline', '%s^..' % args.start])

  regex = re.compile('([0-9a-f]*) (%s): ' % (args.prefix), flags=re.I)
  ret = 0
  for l in reversed(proc.decode('UTF-8').split('\n')):
    this_ret = 0
    m = regex.match(l)
    if m:
      this_ret = review_change(m.group(1), args.verbose, args.chatty)
    if this_ret and (args.verbose or args.chatty):
      print('')
    ret += this_ret

  return ret

if __name__ == '__main__':
  sys.exit(main())

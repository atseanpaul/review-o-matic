#!/usr/bin/env python3

import argparse
import re
import subprocess
import sys

class LineType(object):
  SUBJECT     = 1
  BODY        = 2
  TAG         = 3
  BLANK       = 4
  CHERRY_PICK = 5
  AM_FROM     = 6
  BUG_TEST    = 7


class Line(object):
  def __init__(self, type, contents):
    self.type = type
    self.contents = contents

  def __str__(self):
    return self.contents

class SubjectLine(Line):
  def __init__(self, value):
    self.type = LineType.SUBJECT
    m = re.match('(UPSTREAM|BACKPORT|FROMGIT|CHROMIUM): (.*)', value, re.I)
    if m:
      self.cros_tag = m.group(1)
      self.value = m.group(2)
    else:
      self.cros_tag = None
      self.value = value

  def __str__(self):
    ret = self.value
    if self.cros_tag:
      ret = '{}: {}'.format(self.cros_tag, ret)
    return ret


class TagLine(Line):
  def __init__(self, tag, value):
    self.tag = tag
    self.value = value
    super().__init__(LineType.TAG, str(self))

  def __str__(self):
    return '{}: {}'.format(self.tag, self.value)


class AmLine(Line):
  def __init__(self, tree):
    self.tree = tree
    super().__init__(LineType.AM_FROM, str(self))

  def __str__(self):
    return '(am from {})'.format(self.tree)


def generate_change_id(msg):
  obj = 'tree '
  obj += subprocess.check_output(['git', 'write-tree']).decode('UTF-8')

  parent = subprocess.check_output(['git', 'rev-parse', 'HEAD^0']).decode('UTF-8')
  if parent != '':
    obj += 'parent {}'.format(parent)

  obj += 'author '
  obj += subprocess.check_output(['git', 'var', 'GIT_AUTHOR_IDENT']).decode('UTF-8')


  obj += 'committer '
  obj += subprocess.check_output(['git', 'var', 'GIT_COMMITTER_IDENT']).decode('UTF-8')

  for m in msg:
    obj += '\n{}'.format(str(m))

  output = subprocess.check_output(['git', 'hash-object', '-t', 'commit', '--stdin'],
                                   input=obj, universal_newlines=True,
                                   stderr=subprocess.STDOUT)
  return TagLine('Change-Id', 'I{}'.format(output))
  


def parse_tag(line):
  val = line.strip()

  m = re.match('((Reviewed|Tested|Acked|Signed-off)-by|Cc|Change-Id): (.*)',
               val, re.I)
  if m:
    return TagLine(m.group(1), m.group(3))

  return None


def parse_cherry_pick(line):
  val = line.strip()

  m = re.match('\(cherry picked from commit ([0-9a-f]*)\)', val, flags=re.I)
  if m:
    return Line(LineType.CHERRY_PICK, val)

  return None


def parse_am_from(line):
  val = line.strip()

  m = re.match('.am from (.*).', val, flags=re.I)
  if m:
    return AmLine(m.group(1))

  return None


def parse_bug_test(line):
  val = line.strip()

  m = re.match('(BUG|TEST)=', val, flags=re.I)
  if m:
    return Line(LineType.BUG_TEST, val)

  return None


def parse_commit_msg(msg_lines):
  msg = []
  for line in msg_lines:
    if line.strip() == '':
      msg.append(Line(LineType.BLANK, ''))
      continue

    value = line.rstrip() # Get rid of newlines and trailing spaces

    if len(msg) == 0:
      msg.append(SubjectLine(value))
      continue

    tag = parse_tag(line)
    if tag:
      msg.append(tag)
      continue

    cp = parse_cherry_pick(line)
    if cp:
      msg.append(cp)
      continue

    am = parse_am_from(line)
    if am:
      msg.append(am)
      continue

    bug = parse_bug_test(line)
    if bug:
      msg.append(bug)
      continue

    msg.append(Line(LineType.BODY, value))

  return msg


def find_line(msg, criteria):
  for i, m in enumerate(msg):
    if criteria(m):
      return (i, m)
  return (None, None)

# Removes the line and a trailing blank (if exists)
def remove_line(msg, idx):
  del msg[idx]
  if len(msg) > idx and msg[idx].type == LineType.BLANK:
    del msg[idx]

def output_processed_msg(args, msg):
  # Add cros prefix to subject
  subj_line,_ = find_line(msg, lambda m: m.type == LineType.SUBJECT)
  if subj_line != None:
    msg[subj_line].cros_tag = args.prefix

  # Insert AM_FROM either in-place or below CHERRY_PICK
  if args.tree:
    new_line = AmLine(args.tree)
    line_num,_ = find_line(msg, lambda m: m.type == LineType.AM_FROM)
    if line_num != None:
      remove_line(msg, line_num)
    else:
      line_num,_ = find_line(msg, lambda m: m.type == LineType.CHERRY_PICK)
      line_num += 1
    msg.insert(line_num, new_line)

  # Remove Change-Id if it exists, we'll put it back later
  cid_line,cid = find_line(msg,
                    lambda m: m.type == LineType.TAG and m.tag == 'Change-Id')
  if cid_line != None:
    remove_line(msg, cid_line)
  else:
    cid = generate_change_id(msg)

  # Remove existing BUG,TEST lines (and trailing blank lines)
  while True:
    bug_line,_ = find_line(msg, lambda m: m.type == LineType.BUG_TEST)
    if bug_line == None:
      break

    remove_line(msg, bug_line)

  # Remove any duplicate SoB below the cherry-pick, it'll go at the end
  if args.sob:
    cp_line,_ = find_line(msg, lambda m: m.type == LineType.CHERRY_PICK)
    while cp_line != None:
      sob_line,_ = find_line(msg[cp_line:],
                     lambda m: m.type == LineType.TAG and
                            m.tag.upper() == 'Signed-off-by'.upper() and
                            m.value.strip().upper() == args.sob.strip().upper())
      if sob_line == None:
        break

      remove_line(msg, cp_line + sob_line)


  # Add Bug/Test/Change-Id to the end
  msg.append(Line(LineType.BLANK, ''))
  msg.append(Line(LineType.BUG_TEST, 'BUG={}'.format(args.bug)))
  msg.append(Line(LineType.BUG_TEST, 'TEST={}'.format(args.test)))

  if cid or args.sob:
    msg.append(Line(LineType.BLANK, ''))
  if args.sob:
    msg.append(TagLine('Signed-off-by', args.sob))
  if cid:
    msg.append(cid)

  # print it out!
  for m in msg:
    print(str(m))


def main():
  parser = argparse.ArgumentParser(description='''
    Add CrOS goo to commit range
 
    Usage:
      git filter-branch --msg-filter "backport-o-matic.py --prefix='UPSTREAM' \
        --bug='b:12345' --test='by hand' --sob='Real Name <email>'"
  ''', formatter_class=argparse.RawTextHelpFormatter)
  parser.add_argument('--prefix', default='UPSTREAM', help='subject prefix')
  parser.add_argument('--tree', help='location of git-tree', default=None)
  parser.add_argument('--bug', help='BUG= value', default='None')
  parser.add_argument('--test', help='TEST= value', default='None')
  parser.add_argument('--sob', help='"Name <email>" for SoB', default=None)
  args = parser.parse_args()

  if 'FROMGIT' in args.prefix and not args.tree:
    raise ValueError('--tree must be specified for FROMGIT commits')

  msg = parse_commit_msg(sys.stdin)

  output_processed_msg(args, msg)


if __name__ == '__main__':
  sys.exit(main())

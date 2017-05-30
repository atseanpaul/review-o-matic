#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
import time

class GerritChange(object):
  def __init__(self, cid):
    self.cid = cid
    self.cnum = 0
    self.last_updated = 0
    self.status = 'INCOMPLETE'
    self.reviewed = False
    self.verified = False
    self.ready = False

  def __str__(self):
    return 'C=%s/%d RV=%s VF=%s RD=%s' % (self.cid, self.cnum,
              'Y' if self.reviewed else 'N', 'Y' if self.verified else 'N',
              'Y' if self.ready else 'N')

  def is_merged(self):
    return self.status == 'MERGED'

  def needs_action(self):
    return not self.is_merged() and (not self.reviewed or not self.verified
                                     or not self.ready)

  def update(self):
    if self.is_merged():
      return

    key = str(self.cnum) if self.cnum != 0 else self.cid 
    proc = subprocess.check_output(['gerrit', '--json', 'inspect', key])
    info = json.loads(proc.decode('UTF-8'))[0]

    self.status = info['status']
    self.cnum = int(info['number'])
    self.last_updated = info['lastUpdated']

    self.reviewed = False
    self.verified = False
    self.ready = False

    current = info['currentPatchSet']
    for a in current['approvals']:
      if a['type'] == 'CRVW' and a['value'] == '2':
        self.reviewed = True

      if a['type'] == 'VRIF' and a['value'] == '1':
        self.verified = True

      if a['type'] == 'COMR' and a['value'] == '1':
        self.ready = True


class Submitter(object):
  def __init__(self, cid_filename):
    self.max_ready = 100
    self.changes = []
    with open(cid_filename, 'r') as f:
      for cid in f.read().splitlines():
        c = GerritChange(cid)
        self.changes.append(c)

  def num_changes(self):
    return len(self.changes)

  def submit_changes(self):
    review = []
    verify = []
    ready = []

    merged = 0
    for i,c in enumerate(self.changes):
      sys.stdout.write('\rRunning submitter (%d/%d)' % (i, self.num_changes()))

      c.update()
      if c.is_merged():
        merged += 1
        continue

      if not c.reviewed:
        review.append(str(c.cnum))
      if not c.verified:
        verify.append(str(c.cnum))
      if not c.ready and len(ready) < self.max_ready:
        ready.append(str(c.cnum))

    sys.stdout.write('\r%d Changes:                    \n' % self.num_changes())
    sys.stdout.write('-- %d merged\n' %  merged)
    sys.stdout.write('-- %d marked reviewed\n' % len(review))
    sys.stdout.write('-- %d marked verified\n' % len(verify))
    sys.stdout.write('-- %d marked ready\n' % len(ready))

    if len(review):
      proc = subprocess.check_output(['gerrit', 'review'] + review + ['2'])
    if len(verify):
      proc = subprocess.check_output(['gerrit', 'verify'] + verify + ['1'])
    if len(ready):
      proc = subprocess.check_output(['gerrit', 'ready'] + ready + ['1'])

  def detect_change(self):
    for i,c in enumerate(self.changes):
      sys.stdout.write('\rDetecting changes (%d/%d)' % (i, self.num_changes()))
      c.update()
      if c.needs_action():
        return True
    return False


def main():
  parser = argparse.ArgumentParser(description='Auto review/submit gerrit cls')
  parser.add_argument('--cid_file', required=True,
    help='Path to file with gerrit change-ids (line delimited, in asc order)')
  parser.add_argument('--daemon', action='store_true',
    help='Run in daemon mode, continuously update changes until merged')
  args = parser.parse_args()

  s = Submitter(args.cid_file)
  while True:
    s.submit_changes()
    if not args.daemon:
      break

    while True:
      sys.stdout.write('\rSleeping...                                        ')
      time.sleep(120)
      if s.detect_change():
        break

if __name__ == '__main__':
  sys.exit(main())

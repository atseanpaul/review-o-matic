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

  def mark_reviewed(self):
    subprocess.check_output(['gerrit', 'review', self.cid , '2'])

  def mark_verified(self):
    subprocess.check_output(['gerrit', 'verify', self.cid , '1'])

  def mark_ready(self):
    subprocess.check_output(['gerrit', 'trybotready', self.cid , '1'])
    subprocess.check_output(['gerrit', 'ready', self.cid , '1'])

  def get_deps(self):
    raw = subprocess.check_output(['gerrit', '--raw', 'deps', self.cid]).decode('UTF-8')
    ret = []
    for l in raw.splitlines():
      ret.append(l)
    return ret

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
  def __init__(self, cid_filename, last_cid, review, verify, ready):
    self.review = review
    self.verify = verify
    self.ready = ready

    self.max_in_flight = 100 # 50 for the cq, 50 for the pre-cq
    self.in_flight = []

    self.changes = []
    if cid_filename != None:
      with open(cid_filename, 'r') as f:
        for cid in f.read().splitlines():
          c = GerritChange(cid)
          self.changes.append(c)

    if last_cid != None:
      c = GerritChange(last_cid)
      deps = c.get_deps()
      for d in reversed(deps):
        c = GerritChange(d)
        self.changes.append(c)


  def num_changes(self):
    return len(self.changes)

  def num_in_flight(self):
    return len(self.in_flight)

  def review_changes(self):
    for i,c in enumerate(self.changes):
      sys.stdout.write('\rRunning reviewer (%d/%d)' % (i, self.num_changes()))
      c.update()
      if c.is_merged():
        continue
      if self.review and not c.reviewed:
        c.mark_reviewed()
      if self.verify and not c.verified:
        c.mark_verified()

  def submit_changes(self):
    self.in_flight = []
    merged = 0
    for i,c in enumerate(self.changes):
      if self.num_in_flight() >= self.max_in_flight:
        break

      sys.stdout.write('\rRunning submitter (%d/%d)' % (i, self.num_changes()))
      c.update()
      if c.is_merged():
        merged += 1
        continue

      if self.review and not c.reviewed:
        c.mark_reviewed()
      if self.verify and not c.verified:
        c.mark_verified()
      if self.ready and not c.ready:
        c.mark_ready()

      self.in_flight.append(c)


    sys.stdout.write('\r%d Changes:                                       \n' %
                     self.num_changes())
    sys.stdout.write('-- %d merged\n' %  merged)
    sys.stdout.write('-- %d in flight\n' %  self.num_in_flight())

  def detect_change(self):
    if self.num_in_flight() == 0: # everything is merged, so no detection needed
      return True

    c = self.in_flight[0]
    sys.stdout.write('\rDetecting change (%d - %s)' % (c.cnum, c.cid))
    c.update()
    if c.is_merged() or c.needs_action():
      return True

    return False


def main():
  parser = argparse.ArgumentParser(description='Auto review/submit gerrit cls')
  parser.add_argument('--cid_file', default=None,
    help='Path to file with gerrit change-ids (line delimited, in asc order)')
  parser.add_argument('--last_cid', default=None,
    help='Gerrit change-id of last patch in set')
  parser.add_argument('--daemon', action='store_true',
    help='Run in daemon mode, continuously update changes until merged')
  parser.add_argument('--no-review', action='store_false', dest='review',
    default=True, help='Don\'t mark changes as reviewed')
  parser.add_argument('--no-verify', action='store_false', dest='verify',
    default=True, help='Don\'t mark changes as verified')
  parser.add_argument('--no-ready', action='store_false', dest='ready',
    default=True, help='Don\'t mark changes as ready')
  args = parser.parse_args()

  if args.cid_file == None and args.last_cid == None:
    raise ValueError('You must specify either cid_file or last_cid')

  s = Submitter(args.cid_file, args.last_cid, args.review, args.verify, args.ready)
  first_pass = True
  while True:
    s.submit_changes()
    if s.num_in_flight() == 0:
      sys.stdout.write('\n\nCongratulations, your changes have landed!\n\n')
      return True

    if first_pass:
      s.review_changes()

    first_pass = False
    if not args.daemon:
      break

    while True:
      sys.stdout.write('\rSleeping...                                        ')
      if s.detect_change():
        break
      time.sleep(60)

if __name__ == '__main__':
  sys.exit(main())

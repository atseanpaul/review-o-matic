from trollreview import ReviewType

import collections
import json
import logging

logger = logging.getLogger('rom.troll.stats')

class TrollStats(object):
  def __init__(self, filepath):
    self.stats = collections.defaultdict(dict)
    self.filepath = filepath

    if self.filepath:
      try:
        with open(self.filepath, 'rt') as f:
          file_stats = json.load(f)
        
        # load the stats from the file into memory
        for k,v in file_stats.items():
          if not isinstance(k, str) or not isinstance(v, dict):
            raise ValueError('Malformed stats file expected "{}" '.format(k) +
                             'as string and "{}" as dict'.format(v))
          self.stats[k] = v

      except FileNotFoundError:
        logger.info('Stats file {} missing, will create'.format(self.filepath))

  def update_for_review(self, project, review):
    self.increment(project, 'patches')
    for i in review.issues:
      self.increment(project, i)
    for f in review.feedback:
      self.increment(project, f)

  def increment(self, project, review_type):
    pkey = project.name
    rkey = str(review_type)
    if not self.stats.get(pkey):
      self.stats[pkey] = {rkey: 1}
    elif not self.stats[pkey].get(rkey):
      self.stats[pkey][rkey] = 1
    else:
      self.stats[pkey][rkey] += 1

  def summarize(self, level):
    logger.log(level, 'Summary:')
    for project,stats in self.stats.items():
      logger.log(level, '   Project: {}'.format(project))
      for revtype,value in stats.items():
        logger.log(level, '     {}={}'.format(revtype, value))

  def save(self):
    if not self.filepath:
      return
    logger.debug('Saving stats to {}'.format(self.filepath))
    with open(self.filepath, 'wt') as f:
      json.dump(self.stats, f, sort_keys=True, indent=2)
